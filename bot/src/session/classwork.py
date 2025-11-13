import time as t
import logging

from ..voice_client import vc_manager
from .Session import Session
from configs.logging_config import get_logger

logger = get_logger(__name__)


async def handle_connection(session: Session):
    try:
        logger.debug(f"Handling classwork connection for guild {session.ctx.guild.id}")
        # ボイスチャンネルに接続されていない場合、接続を試みる
        await vc_manager.connect(session)
    except Exception as e:
        logger.error(f"Error handling classwork connection: {e}")
        logger.exception("Exception details:")
        raise


async def update_msg(session: Session):
    try:
        from ..utils import msg_builder

        timer = session.timer
        timer.remaining = timer.end - t.time()
        if not session.bot_start_msg:
            return
        classwork_msg = session.bot_start_msg

        # メッセージを更新（詳細情報を含む）
        embed = msg_builder.classwork_embed(session)
        await classwork_msg.edit(embed=embed)
    except Exception as e:
        logger.error(f"Error updating classwork message: {e}")
        logger.exception("Exception details:")
