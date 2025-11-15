from asyncio import sleep
import logging

from discord import FFmpegPCMAudio, PCMVolumeTransformer

from configs import bot_enum
from ..session.Session import Session
from configs.logging_config import get_logger

logger = get_logger(__name__)


async def alert(session: Session):
    try:
        vc = getattr(session.ctx, 'voice_client', None) or session.ctx.guild.voice_client
        if not vc:
            logger.debug("No voice client available for alert")
            return

        if session.state == bot_enum.State.COUNTDOWN:
            path = bot_enum.AlertPath.POMO_END
        elif session.state == bot_enum.State.POMODORO:
            path = bot_enum.AlertPath.POMO_START
        elif session.state == bot_enum.State.CLASSWORK:
            path = bot_enum.AlertPath.POMO_START
        elif session.state == bot_enum.State.LONG_BREAK:
            path = bot_enum.AlertPath.POMO_END
        else:  # SHORT_BREAK, CLASSWORK_BREAK
            path = bot_enum.AlertPath.LONG_BREAK_START
        
        logger.debug(f"Playing alert sound: {path}")
        source = PCMVolumeTransformer(FFmpegPCMAudio(path, executable='ffmpeg'),
                                      volume=0.1)
        if vc.is_playing():
            vc.stop()
        vc.play(source)
        while vc.is_playing():
            await sleep(1)
        logger.debug("Alert sound finished")
    except Exception as e:
        logger.error(f"Error playing alert: {e}")
        logger.exception("Exception details:")
