import logging

from .Session import Session
from configs import bot_enum
from configs.logging_config import get_logger

logger = get_logger(__name__)


async def transition(session: Session):
    try:
        import time
        
        logger.debug(f"Transitioning state for session in guild {session.ctx.guild.id} from {session.state}")
        session.timer.running = False
        if session.state == bot_enum.State.POMODORO:
            stats = session.stats
            stats.pomos_completed += 1
            stats.pomos_elapsed += 1
            stats.seconds_completed += session.settings.duration * 60
            if stats.pomos_elapsed > 0 and\
                    stats.pomos_elapsed % session.settings.intervals == 0:
                session.state = bot_enum.State.LONG_BREAK
            else:
                session.state = bot_enum.State.SHORT_BREAK
        elif session.state == bot_enum.State.CLASSWORK:
            stats = session.stats
            stats.pomos_completed += 1
            stats.seconds_completed += session.settings.duration * 60
            session.state = bot_enum.State.CLASSWORK_BREAK
            await session.auto_mute.unmute(session.ctx)
        elif session.state == bot_enum.State.CLASSWORK_BREAK:
            session.state = bot_enum.State.CLASSWORK
            await session.auto_mute.mute(session.ctx)
        else:
            session.state = bot_enum.State.POMODORO
            await session.auto_mute.mute(session.ctx)
        session.timer.set_time_remaining()
        # セッション開始時刻を記録
        session.current_session_start_time = time.time()
        logger.debug(f"Transitioned to {session.state} for guild {session.ctx.guild.id}")
    except Exception as e:
        logger.error(f"Error transitioning state: {e}")
        logger.exception("Exception details:")
        raise


async def auto_mute(session: Session):
    try:
        logger.debug(f"Auto mute for session in guild {session.ctx.guild.id} state {session.state}")
        if session.state in bot_enum.State.WORK_STATES:
            await session.auto_mute.mute(session.ctx)
        else:
            await session.auto_mute.unmute(session.ctx)
    except Exception as e:
        logger.error(f"Error in auto mute: {e}")
        logger.exception("Exception details:")
