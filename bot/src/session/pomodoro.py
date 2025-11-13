import time as t
import logging

from .Session import Session
from ..utils.msg_builder import settings_embed
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
        await session.bot_start_msg.edit(embed=updated_embed)
    except Exception as e:
        logger.error(f"Error updating pomodoro message: {e}")
        logger.exception("Exception details:")
