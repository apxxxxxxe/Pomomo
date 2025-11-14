import time
import json
import logging
import os
from typing import Optional, Dict, Any
from pathlib import Path
import aiohttp

from configs.logging_config import get_logger

logger = get_logger(__name__)

# デバッグフラグ - 本番運用時はFalseに設定
# 環境変数 API_DEBUG_LOG_ALL_RESPONSES=true で有効化可能
DEBUG_LOG_ALL_RESPONSES = os.getenv('API_DEBUG_LOG_ALL_RESPONSES', 'false').lower() in ('true', '1', 'yes')

class DiscordAPIMonitor:
    """Discord APIのレスポンスヘッダを監視し、レート制限情報を記録するクラス"""
    
    def __init__(self, log_file_path: str = "logs/api_headers.jsonl", 
                 max_bytes: int = 10 * 1024 * 1024, backup_count: int = 7):
        """
        Args:
            log_file_path: APIヘッダ情報を記録するファイルパス
            max_bytes: ログファイルの最大サイズ（バイト）デフォルト10MB
            backup_count: 保持するバックアップファイル数（デフォルト7個）
        """
        self.log_file_path = Path(log_file_path)
        self.log_file_path.parent.mkdir(exist_ok=True)
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self._original_request = None
        self._is_hooked = False
    
    def _extract_rate_limit_headers(self, headers: Dict[str, str]) -> Dict[str, Any]:
        """レート制限関連のヘッダ情報を抽出する"""
        rate_limit_info = {}
        
        # Discord APIのレート制限ヘッダを抽出
        header_mappings = {
            'x-ratelimit-limit': 'limit',
            'x-ratelimit-remaining': 'remaining', 
            'x-ratelimit-reset': 'reset',
            'x-ratelimit-reset-after': 'reset_after',
            'x-ratelimit-bucket': 'bucket',
            'x-ratelimit-scope': 'scope',
            'retry-after': 'retry_after',
        }
        
        for header_key, info_key in header_mappings.items():
            if header_key in headers:
                value = headers[header_key]
                # 数値のヘッダは適切に変換
                if info_key in ['limit', 'remaining', 'reset', 'reset_after', 'retry_after']:
                    try:
                        value = float(value) if '.' in value else int(value)
                    except (ValueError, TypeError):
                        pass
                rate_limit_info[info_key] = value
        
        return rate_limit_info
    
    def _should_rotate(self) -> bool:
        """ログファイルをローテーションする必要があるかチェック"""
        try:
            if not self.log_file_path.exists():
                return False
            return self.log_file_path.stat().st_size >= self.max_bytes
        except OSError:
            return False
    
    def _rotate_log_file(self):
        """ログファイルをローテーションする"""
        if not self.log_file_path.exists():
            return
        
        try:
            # 既存のバックアップファイルをシフト
            for i in range(self.backup_count - 1, 0, -1):
                old_backup = self.log_file_path.with_suffix(f".{i}.jsonl")
                new_backup = self.log_file_path.with_suffix(f".{i+1}.jsonl")
                
                if old_backup.exists():
                    if new_backup.exists():
                        new_backup.unlink()
                    old_backup.rename(new_backup)
            
            # 現在のファイルを .1 にリネーム
            first_backup = self.log_file_path.with_suffix(".1.jsonl")
            if first_backup.exists():
                first_backup.unlink()
            self.log_file_path.rename(first_backup)
            
            logger.info(f"API headers log rotated: {self.log_file_path}")
            
        except OSError as e:
            logger.error(f"Failed to rotate API headers log: {e}")
    
    def _write_log_entry(self, log_entry: Dict[str, Any]):
        """ログエントリをファイルに書き込む（ローテーション機能付き）"""
        try:
            # ローテーションが必要かチェック
            if self._should_rotate():
                self._rotate_log_file()
            
            # JSONLines形式でログファイルに追記
            with open(self.log_file_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
                
        except Exception as e:
            logger.error(f"Error writing to API headers log: {e}")
    
    def log_manual_edit_attempt(self, operation_type: str, duration: float, success: bool = True, 
                               error_msg: str = None):
        """手動でメッセージ編集の試行を記録する（HTTPフック無しの代替手段）"""
        try:
            # デバッグフラグが無効で、成功した場合はログを記録しない
            if not DEBUG_LOG_ALL_RESPONSES and success:
                return
            
            log_entry = {
                'timestamp': time.time(),
                'iso_timestamp': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()),
                'method': 'PATCH',
                'url': 'discord_message_edit',
                'status_code': 200 if success else 500,
                'operation_type': operation_type,
                'duration_ms': round(duration * 1000, 2),
                'success': success,
                'error': error_msg,
                'manual_log': True  # 手動ログであることを示すフラグ
            }
            
            # ローテーション機能付きでログエントリを書き込み
            self._write_log_entry(log_entry)
                
            if not success and error_msg:
                logger.warning(f"Message edit failed - {operation_type}: {error_msg}")
                
        except Exception as e:
            logger.error(f"Error logging manual edit attempt: {e}")
    
    def log_api_response(self, method: str, url: str, status_code: int, headers: Dict[str, str], 
                        operation_type: str = "unknown"):
        """APIレスポンス情報をログに記録する"""
        try:
            # デバッグフラグが無効で、ステータスコードが200の場合はログを記録しない
            if not DEBUG_LOG_ALL_RESPONSES and status_code == 200:
                # ただし、レート制限に関する重要な情報がある場合は記録する
                rate_limit_info = self._extract_rate_limit_headers(headers)
                remaining = rate_limit_info.get('remaining')
                
                # 残り回数が少ない場合（5未満）や429エラーの場合は記録する
                if not (isinstance(remaining, (int, float)) and remaining < 5):
                    return
            
            rate_limit_info = self._extract_rate_limit_headers(headers)
            
            log_entry = {
                'timestamp': time.time(),
                'iso_timestamp': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()),
                'method': method,
                'url': url,
                'status_code': status_code,
                'operation_type': operation_type,
                'rate_limit': rate_limit_info,
            }
            
            # ローテーション機能付きでログエントリを書き込み
            self._write_log_entry(log_entry)
            
            # レート制限に関する情報をログ出力
            if rate_limit_info:
                remaining = rate_limit_info.get('remaining', 'unknown')
                limit = rate_limit_info.get('limit', 'unknown')
                reset_after = rate_limit_info.get('reset_after', 'unknown')
                
                logger.debug(f"API Rate Limit - {operation_type}: {remaining}/{limit} remaining, "
                           f"reset in {reset_after}s")
                
                # 残り回数が少ない場合は警告
                if isinstance(remaining, (int, float)) and remaining < 5:
                    logger.warning(f"API Rate Limit low - {operation_type}: {remaining} requests remaining")
                    
                # 429エラーの場合は詳細ログ
                if status_code == 429:
                    retry_after = rate_limit_info.get('retry_after', 'unknown')
                    logger.error(f"Rate limit exceeded - {operation_type}: retry after {retry_after}s")
                    
        except Exception as e:
            logger.error(f"Error logging API response: {e}")
    
    def hook_discord_http(self, http_client):
        """discord.pyのHTTPクライアントにレスポンス監視フックを追加する"""
        if self._is_hooked:
            return
            
        try:
            # 元のrequestメソッドを保存
            self._original_request = http_client.request
            
            # discord.pyのHTTPClient.requestメソッドをラップ
            async def hooked_request(route, **kwargs):
                """
                discord.pyのHTTPClient.requestメソッドのラッパー
                引数:
                    route: discord.Route オブジェクト
                    **kwargs: その他のパラメータ（json, dataなど）
                """
                # デバッグ: フックが呼ばれたことをログ出力
                logger.debug(f"HTTP hook called: route={route}, kwargs keys={list(kwargs.keys())}")
                
                # RouteオブジェクトからHTTPメソッドとURLを取得
                method = route.method if hasattr(route, 'method') else 'UNKNOWN'
                url = route.url if hasattr(route, 'url') else 'unknown'
                
                logger.debug(f"Extracted method={method}, url={url}")
                
                operation_type = self._get_operation_type(str(method), str(url))
                
                try:
                    # 元のリクエストを実行
                    response = await self._original_request(route, **kwargs)
                    
                    # レスポンスオブジェクトから情報を取得
                    logger.debug(f"Response type: {type(response)}")
                    
                    # レスポンスが辞書の場合（JSONレスポンス）
                    # discord.pyは既にレスポンスを処理してJSONに変換している
                    # この時点ではヘッダー情報は失われている
                    if isinstance(response, dict):
                        logger.debug("Response is already parsed JSON - headers not available at this level")
                        # 手動ログのみに依存する必要がある
                        self.log_manual_edit_attempt(
                            operation_type=operation_type,
                            duration=0.0,  # 実際の時間は測定できない
                            success=True,
                            error_msg=None
                        )
                    # aiohttpのClientResponseオブジェクトの場合
                    elif hasattr(response, 'status') and hasattr(response, 'headers'):
                        # ヘッダーを辞書に変換（大文字小文字を正規化）
                        headers = {}
                        for key, value in response.headers.items():
                            headers[key.lower()] = value
                        
                        logger.debug(f"Headers found: {list(headers.keys())}")
                        
                        self.log_api_response(
                            method=str(method),
                            url=str(url),
                            status_code=response.status,
                            headers=headers,
                            operation_type=operation_type
                        )
                    else:
                        logger.debug(f"Unexpected response type: {type(response)}")
                    
                    return response
                    
                except Exception as e:
                    # HTTPExceptionやその他のエラーの処理
                    status_code = 0
                    headers = {}
                    
                    # discord.HTTPExceptionの場合
                    if hasattr(e, 'response'):
                        resp = e.response
                        if hasattr(resp, 'status'):
                            status_code = resp.status
                        if hasattr(resp, 'headers'):
                            headers = dict(resp.headers)
                    
                    # 直接statusとheadersを持っている場合
                    if hasattr(e, 'status'):
                        status_code = e.status
                    if hasattr(e, 'headers'):
                        headers = dict(e.headers)
                    
                    self.log_api_response(
                        method=str(method),
                        url=str(url),
                        status_code=status_code,
                        headers=headers,
                        operation_type=f"{operation_type}_error"
                    )
                    
                    raise
            
            # HTTPクライアントのrequestメソッドを置き換え
            logger.info(f"Original request method: {self._original_request}")
            http_client.request = hooked_request
            logger.info(f"Hooked request method: {http_client.request}")
            self._is_hooked = True
            
            logger.info("Discord HTTP client hooked for API monitoring")
            
        except Exception as e:
            logger.error(f"Failed to hook Discord HTTP client: {e}")
            logger.exception("Exception details:")
    
    def _get_operation_type(self, method: str, url: str) -> str:
        """URLとメソッドから操作タイプを推定する"""
        url_str = str(url).lower()
        
        if 'messages' in url_str:
            if method.upper() == 'PATCH':
                return 'message_edit'
            elif method.upper() == 'POST':
                return 'message_send'
            elif method.upper() == 'DELETE':
                return 'message_delete'
        elif 'channels' in url_str:
            if 'pins' in url_str:
                return 'message_pin'
            return 'channel_operation'
        elif 'guilds' in url_str:
            if 'members' in url_str:
                return 'member_operation'
            return 'guild_operation'
        
        return f"{method.lower()}_request"

# グローバルインスタンス
_api_monitor = None

def get_api_monitor() -> DiscordAPIMonitor:
    """APIモニタのシングルトンインスタンスを取得"""
    global _api_monitor
    if _api_monitor is None:
        # 環境変数からローテーション設定を取得
        max_bytes = int(os.getenv('API_LOG_MAX_BYTES', '10485760'))  # 10MB
        backup_count = int(os.getenv('API_LOG_BACKUP_COUNT', '7'))
        log_path = os.getenv('API_LOG_PATH', 'logs/api_headers.jsonl')
        
        _api_monitor = DiscordAPIMonitor(
            log_file_path=log_path,
            max_bytes=max_bytes,
            backup_count=backup_count
        )
    return _api_monitor

def setup_api_monitoring(bot_instance, enable_hook=False):
    """Discordボットのインスタンスに対してAPIモニタリングを設定"""
    try:
        monitor = get_api_monitor()
        logger.info(f"Setting up API monitoring, enable_hook={enable_hook}, has http={hasattr(bot_instance, 'http')}")
        logger.info(f"API monitoring debug mode: {DEBUG_LOG_ALL_RESPONSES}")
        
        if hasattr(bot_instance, 'http') and enable_hook:
            logger.info(f"HTTP client type: {type(bot_instance.http)}")
            logger.info(f"HTTP client request method: {type(bot_instance.http.request)}")
            monitor.hook_discord_http(bot_instance.http)
            logger.info("API monitoring with HTTP hook setup completed")
        else:
            logger.info("API monitoring setup completed (HTTP hook disabled)")
            if not hasattr(bot_instance, 'http'):
                logger.warning("Bot instance does not have HTTP client attribute")
    except Exception as e:
        logger.error(f"Failed to setup API monitoring: {e}")
        logger.warning("API monitoring will continue without HTTP hook")