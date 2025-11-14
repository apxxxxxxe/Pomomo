#!/usr/bin/env python3
"""
Discord API Rate Limitログ分析スクリプト

使用方法:
    python analyze_api_logs.py logs/api_headers.jsonl
    
出力:
    - レート制限統計情報
    - 429エラー発生パターン
    - 適切な更新頻度の推奨値
"""

import json
import argparse
import statistics
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from typing import List, Dict, Any

def load_api_logs(file_path: str) -> List[Dict[str, Any]]:
    """APIログファイルを読み込む（ローテーションされたファイルも含む）"""
    logs = []
    
    # メインファイルとローテーションされたファイルのパスを取得
    main_path = Path(file_path)
    log_files = [main_path]
    
    # ローテーションされたファイルを検索 (.1.jsonl, .2.jsonl, ...)
    for i in range(1, 31):  # 最大30個のバックアップファイルを検索
        backup_path = main_path.with_suffix(f".{i}.jsonl")
        if backup_path.exists():
            log_files.append(backup_path)
        else:
            break
    
    print(f"読み込み対象ファイル: {len(log_files)}個")
    for log_file in log_files:
        print(f"  - {log_file}")
    
    # 各ファイルからログを読み込み
    for log_file in log_files:
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if line:
                        try:
                            log_entry = json.loads(line)
                            logs.append(log_entry)
                        except json.JSONDecodeError as e:
                            print(f"JSON parsing error in {log_file}:{line_num}: {e}")
                            continue
        except FileNotFoundError:
            if log_file == main_path:
                print(f"メインログファイル {file_path} が見つかりません")
                return []
            else:
                print(f"バックアップファイル {log_file} をスキップ")
                continue
        except Exception as e:
            print(f"ファイル読み込みエラー {log_file}: {e}")
            continue
    
    print(f"総ログエントリ数: {len(logs)}")
    return logs

def analyze_rate_limits(logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """レート制限情報を分析"""
    # メッセージ編集関連のログを抽出（手動ログも含む）
    message_edit_logs = [log for log in logs if 
                        'message_edit' in log.get('operation_type', '') or 
                        log.get('manual_log') == True]
    
    if not message_edit_logs:
        return {"error": "メッセージ編集のログが見つかりません"}
    
    analysis = {
        "total_edit_requests": len(message_edit_logs),
        "rate_limit_hits": 0,
        "low_remaining_warnings": 0,
        "remaining_counts": [],
        "reset_times": [],
        "time_intervals": [],
        "status_codes": Counter()
    }
    
    # 時系列でソート
    message_edit_logs.sort(key=lambda x: x.get('timestamp', 0))
    
    prev_timestamp = None
    
    for log in message_edit_logs:
        rate_limit = log.get('rate_limit', {})
        status_code = log.get('status_code')
        timestamp = log.get('timestamp')
        
        # ステータスコード統計
        analysis["status_codes"][status_code] += 1
        
        # 429エラー（レート制限）の検出
        if status_code == 429:
            analysis["rate_limit_hits"] += 1
        
        # 手動ログの場合の失敗の検出
        if log.get('manual_log') and not log.get('success', True):
            analysis["rate_limit_hits"] += 1  # 失敗をレート制限として扱う
        
        # 残り回数の統計
        remaining = rate_limit.get('remaining')
        if isinstance(remaining, (int, float)):
            analysis["remaining_counts"].append(remaining)
            if remaining < 5:
                analysis["low_remaining_warnings"] += 1
        
        # リセット時間の統計
        reset_after = rate_limit.get('reset_after')
        if isinstance(reset_after, (int, float)):
            analysis["reset_times"].append(reset_after)
        
        # リクエスト間隔の計算
        if prev_timestamp and timestamp:
            interval = timestamp - prev_timestamp
            analysis["time_intervals"].append(interval)
        
        prev_timestamp = timestamp
    
    # 統計値の計算
    if analysis["remaining_counts"]:
        analysis["remaining_stats"] = {
            "min": min(analysis["remaining_counts"]),
            "max": max(analysis["remaining_counts"]),
            "avg": statistics.mean(analysis["remaining_counts"]),
            "median": statistics.median(analysis["remaining_counts"])
        }
    
    if analysis["time_intervals"]:
        analysis["interval_stats"] = {
            "min": min(analysis["time_intervals"]),
            "max": max(analysis["time_intervals"]),
            "avg": statistics.mean(analysis["time_intervals"]),
            "median": statistics.median(analysis["time_intervals"])
        }
    
    if analysis["reset_times"]:
        analysis["reset_stats"] = {
            "min": min(analysis["reset_times"]),
            "max": max(analysis["reset_times"]),
            "avg": statistics.mean(analysis["reset_times"])
        }
    
    return analysis

def generate_recommendations(analysis: Dict[str, Any]) -> List[str]:
    """分析結果に基づく推奨事項を生成"""
    recommendations = []
    
    if analysis.get("error"):
        recommendations.append("❌ ログデータが不足しています")
        return recommendations
    
    # レート制限エラーの分析
    rate_limit_hits = analysis.get("rate_limit_hits", 0)
    total_requests = analysis.get("total_edit_requests", 0)
    
    if rate_limit_hits > 0:
        error_rate = (rate_limit_hits / total_requests) * 100
        recommendations.append(f"⚠️ {rate_limit_hits}回のレート制限エラーが発生（エラー率: {error_rate:.2f}%）")
        
        # 間隔調整の推奨
        if "interval_stats" in analysis:
            current_avg = analysis["interval_stats"]["avg"]
            recommended_interval = max(current_avg * 1.5, 2.0)  # 現在の1.5倍以上、最低2秒
            recommendations.append(f"📊 推奨更新間隔: {recommended_interval:.1f}秒以上（現在平均: {current_avg:.1f}秒）")
    else:
        recommendations.append("✅ レート制限エラーは発生していません")
    
    # 残り回数の警告分析
    low_remaining = analysis.get("low_remaining_warnings", 0)
    if low_remaining > 0:
        recommendations.append(f"⚠️ 残り回数が少ない警告: {low_remaining}回")
        recommendations.append("💡 更新頻度を下げることを検討してください")
    
    # 最適化提案
    if "remaining_stats" in analysis:
        avg_remaining = analysis["remaining_stats"]["avg"]
        if avg_remaining > 20:
            recommendations.append("💡 レート制限に余裕があります。更新頻度を上げることも可能です")
        elif avg_remaining < 10:
            recommendations.append("⚠️ レート制限の使用率が高いです。更新頻度を下げることを推奨します")
    
    # 現在の更新パターン分析
    if "interval_stats" in analysis:
        min_interval = analysis["interval_stats"]["min"]
        if min_interval < 1.0:
            recommendations.append("⚠️ 1秒未満の短い間隔で更新されています。Discord APIガイドラインに注意してください")
    
    return recommendations

def print_analysis_report(analysis: Dict[str, Any], recommendations: List[str]):
    """分析レポートを出力"""
    print("=" * 60)
    print("Discord API Rate Limit 分析レポート")
    print("=" * 60)
    print()
    
    if analysis.get("error"):
        print("❌ エラー:", analysis["error"])
        return
    
    # 基本統計
    print("📊 基本統計:")
    print(f"  総メッセージ編集リクエスト数: {analysis['total_edit_requests']}")
    print(f"  レート制限エラー(429)回数: {analysis['rate_limit_hits']}")
    print(f"  低残り回数警告: {analysis['low_remaining_warnings']}")
    print()
    
    # ステータスコード分布
    print("📈 ステータスコード分布:")
    for status_code, count in analysis["status_codes"].most_common():
        percentage = (count / analysis["total_edit_requests"]) * 100
        print(f"  {status_code}: {count}回 ({percentage:.1f}%)")
    print()
    
    # レート制限統計
    if "remaining_stats" in analysis:
        stats = analysis["remaining_stats"]
        print("🔢 残りリクエスト数統計:")
        print(f"  最小: {stats['min']}")
        print(f"  最大: {stats['max']}")
        print(f"  平均: {stats['avg']:.2f}")
        print(f"  中央値: {stats['median']:.2f}")
        print()
    
    # 更新間隔統計
    if "interval_stats" in analysis:
        stats = analysis["interval_stats"]
        print("⏱️ 更新間隔統計（秒）:")
        print(f"  最短: {stats['min']:.3f}")
        print(f"  最長: {stats['max']:.3f}")
        print(f"  平均: {stats['avg']:.3f}")
        print(f"  中央値: {stats['median']:.3f}")
        print()
    
    # リセット時間統計
    if "reset_stats" in analysis:
        stats = analysis["reset_stats"]
        print("🔄 リセット時間統計（秒）:")
        print(f"  最短: {stats['min']:.2f}")
        print(f"  最長: {stats['max']:.2f}")
        print(f"  平均: {stats['avg']:.2f}")
        print()
    
    # 推奨事項
    print("💡 推奨事項:")
    for rec in recommendations:
        print(f"  {rec}")
    print()

def main():
    parser = argparse.ArgumentParser(description="Discord API Rate Limitログを分析します")
    parser.add_argument("log_file", nargs="?", default="logs/api_headers.jsonl", 
                       help="ログファイルのパス（デフォルト: logs/api_headers.jsonl）")
    parser.add_argument("--json", action="store_true", 
                       help="結果をJSON形式で出力")
    
    args = parser.parse_args()
    
    if not Path(args.log_file).exists():
        print(f"❌ ログファイル {args.log_file} が見つかりません")
        print("ボットを実行してAPIログを生成してから再度実行してください")
        return 1
    
    # ログの読み込みと分析
    logs = load_api_logs(args.log_file)
    if not logs:
        print("❌ 有効なログデータが見つかりません")
        return 1
    
    analysis = analyze_rate_limits(logs)
    recommendations = generate_recommendations(analysis)
    
    if args.json:
        # JSON形式で出力
        output = {
            "analysis": analysis,
            "recommendations": recommendations
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        # 人間向けレポート
        print_analysis_report(analysis, recommendations)
    
    return 0

if __name__ == "__main__":
    exit(main())