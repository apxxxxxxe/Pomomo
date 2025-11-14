import time as t
import logging

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
        
        try:
            await session.bot_start_msg.edit(embed=updated_embed)
        except Exception as edit_error:
            success = False
            error_msg = str(edit_error)
            raise
        finally:
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
