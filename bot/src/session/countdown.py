import time as t
from asyncio import sleep
import logging

from discord import Colour

from ..voice_client import vc_accessor, vc_manager
from . import session_manager, session_controller
from .Session import Session
from ..utils import player
from configs.logging_config import get_logger
from configs.config import MESSAGE_UPDATE_INTERVAL_SECONDS

logger = get_logger(__name__)


async def handle_connection(session: Session, audio_alert: str):
    try:
        if audio_alert != 'mute':
            # ボイスチャンネルに接続されていない場合、接続を試みる
            await vc_manager.connect(session)
        else:
            # mute モードの場合、ボイスチャンネルから切断し、フラグを設定
            session.is_muted_mode = True
            vc = vc_accessor.get_voice_client(session.ctx)
            if vc:
                await vc.disconnect()
    except Exception as e:
        logger.error(f"Error handling countdown connection: {e}")
        logger.exception("Exception details:")
        raise


async def update_msg(session: Session):
    try:
        timer = session.timer
        timer.remaining = timer.end - t.time()
        if not session.bot_start_msg:
            return
        countdown_msg = session.bot_start_msg
        embed = countdown_msg.embeds[0]
        if timer.remaining < 0:
            embed.colour = Colour.red()
            embed.description = '終了!'
            # mute モードでない場合のみ unmute を実行
            if not getattr(session, 'is_muted_mode', False):
                await session.auto_mute.unmute(session.ctx)
            await countdown_msg.edit(embed=embed)
            await session.dm.send_dm(embed=embed)
            await player.alert(session)
            await session_controller.end(session)
            return
        embed.description = f'**残り{timer.time_remaining_to_str(hi_rez=True)}**'
        await countdown_msg.edit(embed=embed)
    except Exception as e:
        logger.error(f"Error updating countdown message: {e}")
        logger.exception("Exception details:")


async def start(session: Session):
    try:
        import time
        logger.info(f"Starting countdown for guild {session.ctx.guild.id}")
        session.timer.running = True
        session.timer.end = time.time() + session.timer.remaining
        last_update = 0
        while True:
            time_remaining = session.timer.remaining
            await sleep(1)
            session = session_manager.active_sessions.get(session_manager.session_id_from(session.ctx))
            if not (session and
                    session.timer.running and
                    time_remaining == session.timer.remaining):
                break
            # メッセージ更新間隔に従って更新
            current_time = time.time()
            if current_time - last_update >= MESSAGE_UPDATE_INTERVAL_SECONDS:
                await update_msg(session)
                last_update = current_time
    except Exception as e:
        logger.error(f"Error in countdown start: {e}")
        logger.exception("Exception details:")
