import time as t
import logging
import asyncio
from discord.errors import DiscordServerError, HTTPException

from .Session import Session
from ..utils.msg_builder import settings_embed
from ..utils.api_monitor import get_api_monitor
from configs.logging_config import get_logger

logger = get_logger(__name__)


async def update_msg(session: Session):
    try:
        timer = session.timer
        timer.remaining = timer.end - t.time()
        if not session.bot_start_msg:
            return
        
        if timer.remaining < 0:
            # タイマー終了時の処理はsession_controllerで行われるため、ここでは何もしない
            return
        
        # settings_embedで統一された埋め込みを取得して更新
        updated_embed = settings_embed(session)
        
        # メッセージ編集の実行と監視
        monitor = get_api_monitor()
        start_time = t.time()
        success = True
        error_msg = None
        
        # リトライロジックを追加
        max_retries = 3
        retry_delay = 1.0  # 初期遅延時間（秒）
        
        for attempt in range(max_retries):
            try:
                await session.bot_start_msg.edit(embed=updated_embed)
                break  # 成功したらループを抜ける
            except (DiscordServerError, HTTPException) as edit_error:
                # 503エラーまたはその他のHTTPエラーの場合
                if attempt < max_retries - 1:
                    # 最後の試行でなければリトライ
                    if isinstance(edit_error, DiscordServerError) and edit_error.status == 503:
                        logger.warning(f"503 error on attempt {attempt + 1}, retrying in {retry_delay}s...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # 指数バックオフ
                    else:
                        # その他のHTTPエラーはリトライしない
                        success = False
                        error_msg = str(edit_error)
                        raise
                else:
                    # 最後の試行で失敗
                    success = False
                    error_msg = str(edit_error)
                    logger.error(f"Failed to update message after {max_retries} attempts: {edit_error}")
                    raise
            except Exception as edit_error:
                # その他の予期しないエラー
                success = False
                error_msg = str(edit_error)
                raise
        
        # 編集操作の実行時間をログ出力
        edit_duration = t.time() - start_time
        logger.debug(f"Pomodoro message edit took {edit_duration:.3f}s")
        
        # APIモニタに手動ログを記録
        monitor.log_manual_edit_attempt(
            operation_type="pomodoro_message_edit",
            duration=edit_duration,
            success=success,
            error_msg=error_msg
        )
    except Exception as e:
        logger.error(f"Error updating pomodoro message: {e}")
        logger.exception("Exception details:")
