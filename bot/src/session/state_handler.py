from .Session import Session
from configs import bot_enum


async def transition(session: Session):
    session.timer.running = False
    if session.state == bot_enum.State.POMODORO:
        stats = session.stats
        stats.pomos_completed += 1
        stats.minutes_completed += session.settings.duration
        if stats.pomos_completed > 0 and\
                stats.pomos_completed % session.settings.intervals == 0:
            session.state = bot_enum.State.LONG_BREAK
        else:
            session.state = bot_enum.State.SHORT_BREAK
    else:
        session.state = bot_enum.State.POMODORO
        await session.auto_mute.mute(session.ctx)
    session.timer.set_time_remaining()
    alert = f'{session.timer.time_remaining_to_str(singular=True)}の{session.state}を開始します。'
    if hasattr(session.ctx, 'send'):  # Context
        await session.ctx.send(alert)
    else:  # Interaction
        if not session.ctx.response.is_done():
            await session.ctx.response.send_message(alert)
        else:
            await session.ctx.followup.send(alert)
    await session.dm.send_dm(alert)


async def auto_mute(session: Session):
    if session.state in [bot_enum.State.COUNTDOWN, bot_enum.State.POMODORO]:
        await session.auto_mute.mute(session.ctx)
    else:
        await session.auto_mute.unmute(session.ctx)
