"""
aiohttpレベルでHTTPレスポンスをフックするモジュール
discord.pyが内部で使用するaiohttpセッションを直接フックする
"""

import time
import json
import logging
from pathlib import Path
from typing import Optional
import aiohttp
from aiohttp import ClientSession, ClientResponse

from configs.logging_config import get_logger

logger = get_logger(__name__)

class AiohttpResponseMonitor:
    """aiohttpのレスポンスを監視してヘッダ情報を記録"""
    
    def __init__(self, log_file_path: str = "logs/api_headers.jsonl"):
        self.log_file_path = Path(log_file_path)
        self.log_file_path.parent.mkdir(exist_ok=True)
        self._original_request = None
        self._hooked_sessions = set()
    
    def log_response(self, method: str, url: str, status: int, headers: dict):
        """レスポンス情報をログに記録"""
        try:
            # レート制限ヘッダを抽出
            rate_limit_info = {}
            for key, value in headers.items():
                lower_key = key.lower()
                if 'x-ratelimit' in lower_key or 'retry-after' in lower_key:
                    rate_limit_info[lower_key] = value
            
            log_entry = {
                'timestamp': time.time(),
                'iso_timestamp': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()),
                'method': method,
                'url': str(url),
                'status_code': status,
                'rate_limit': rate_limit_info,
                'aiohttp_hook': True
            }
            
            # JSONLines形式で保存
            with open(self.log_file_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
            
            # レート制限情報をログ出力
            if rate_limit_info:
                remaining = rate_limit_info.get('x-ratelimit-remaining', 'unknown')
                limit = rate_limit_info.get('x-ratelimit-limit', 'unknown')
                logger.debug(f"[aiohttp] Rate limit: {remaining}/{limit} remaining")
                
        except Exception as e:
            logger.error(f"Error logging aiohttp response: {e}")
    
    def hook_session(self, session: ClientSession):
        """aiohttpセッションにフックを設定"""
        if id(session) in self._hooked_sessions:
            return
        
        try:
            original_request = session._request
            monitor = self
            
            async def hooked_request(method, url, **kwargs):
                """aiohttpのリクエストをフック"""
                # 元のリクエストを実行
                response = await original_request(method, url, **kwargs)
                
                # レスポンス情報を記録
                if isinstance(response, ClientResponse):
                    monitor.log_response(
                        method=method,
                        url=url,
                        status=response.status,
                        headers=dict(response.headers)
                    )
                
                return response
            
            session._request = hooked_request
            self._hooked_sessions.add(id(session))
            logger.info(f"aiohttp session hooked: {session}")
            
        except Exception as e:
            logger.error(f"Failed to hook aiohttp session: {e}")

def setup_aiohttp_monitoring(bot_instance):
    """Discord botのaiohttpセッションをフック"""
    try:
        monitor = AiohttpResponseMonitor()
        
        # discord.pyのHTTPクライアントが持つaiohttpセッションにアクセス
        if hasattr(bot_instance, 'http'):
            http_client = bot_instance.http
            
            # _HTTPClient__sessionという名前でプライベート属性にアクセス
            if hasattr(http_client, '_HTTPClient__session'):
                session = http_client._HTTPClient__session
                if session:
                    monitor.hook_session(session)
                    logger.info("aiohttp monitoring setup completed")
                    return True
                else:
                    logger.warning("aiohttp session not yet initialized")
            else:
                logger.warning("Cannot find aiohttp session in HTTPClient")
        
        return False
        
    except Exception as e:
        logger.error(f"Failed to setup aiohttp monitoring: {e}")
        return False