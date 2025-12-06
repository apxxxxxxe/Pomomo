# CLAUDE.md

**ユーザーへの応答は日本語で行うこと**

このファイルは、このリポジトリのコードを操作する際にClaude Code (claude.ai/code) にガイダンスを提供します。

## プロジェクト概要

Pomomoは、Discord上でPomodoro技術を実装するボットです。作業と休憩の間隔を管理し、生産性向上を支援します。Python 3.11とdiscord.py 1.6.0を使用して構築されています。

## 開発コマンド

### 環境セットアップ
```bash
# 仮想環境作成
python -m venv venv

# 依存関係インストール
pip install -r requirements.txt

# 環境変数設定（.envファイルに以下を設定）
DISCORD_TOKEN=your_discord_bot_token
```

### ボット実行
```bash
# メイン実行方法
cd bot && python main.py
```

### 開発時の確認コマンド
```bash
# Python環境確認
python --version

# 依存関係一覧
pip list

# 構文チェック
python -m pylint bot/main.py
```

## アーキテクチャ

### コア構造
- **bot/main.py**: エントリーポイント、Cogsの読み込み
- **bot/configs/**: 設定ファイル群（config.py、bot_enum.py等）
- **bot/cogs/**: Discord.pyのCogsパターンによるコマンド実装
  - control.py: メイン制御コマンド（start、pause、resume等）
  - info.py: 情報取得コマンド（status、stats等）
  - subscribe.py: サブスクリプション機能
- **bot/src/**: コアビジネスロジック
  - session/: セッション管理（Session.py、session_manager.py等）
  - subscriptions/: DM通知、自動ミュート機能
  - voice_client/: Discord音声クライアント管理
  - utils/: メッセージ構築、音声再生ユーティリティ

### 重要なクラス
- **Session**: Pomodoroセッション状態管理
- **Timer**: タイマー機能実装
- **Settings**: セッション設定管理
- **Stats**: セッション統計情報

## コーディング規約

### 命名規則
- クラス: PascalCase (例: Session, Timer)
- 関数/変数: snake_case (例: active_sessions, kill_if_idle)
- 定数: UPPER_SNAKE_CASE (例: CMD_PREFIX, TIMEOUT_SECONDS)

### プロジェクト固有の重要点
- セッション管理は`session_manager.py`で中央管理
- 音声機能はPyNaClライブラリを使用
- 非同期処理（async/await）の適切な使用が必須
- Discord Intentsの明示的設定が必要
- コマンドプレフィックスは設定ファイルで管理（現在は'test!'）

### ファイル編集時の注意
- 既存のdiscord.pyパターン（Cogs）に従う
- セッション状態の整合性を保つ
- 音声処理部分は慎重に変更する
- 環境変数の取り扱いに注意（.envファイル使用）

## 完了時チェックリスト

1. 構文エラーの確認: `python -m py_compile`で主要ファイルをチェック
2. ボット起動確認: `python bot/main.py`で正常起動を確認
3. 基本機能確認: Discordでボットがオンラインになることを確認
4. 環境変数確認: DISCORD_TOKENが正しく設定されていることを確認
5. 依存関係確認: requirements.txtに新しい依存関係があれば追加

注意: このプロジェクトには自動テスト、lint、formatツールは設定されていません。手動でのコード品質チェックが必要です。
