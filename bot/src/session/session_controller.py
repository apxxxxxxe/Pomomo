import time as t
from asyncio import sleep

from . import session_manager, session_messenger, countdown, state_handler
from .Session import Session
from ..Settings import Settings
from ..utils import player
from ..voice_client import vc_accessor, vc_manager
from configs import config, bot_enum


async def resume(session: Session):
    session.timeout = int(t.time() + config.TIMEOUT_SECONDS)
    await state_handler.auto_mute(session)
    if session.state == bot_enum.State.COUNTDOWN:
        await countdown.start(session)
        return
    while True:
        if not await run_interval(session):
            break


async def start(session: Session):
    print("DEBUG: session_controller.start called")
    try:
        print("DEBUG: Calling vc_manager.connect")
        if not await vc_manager.connect(session):
            print("DEBUG: vc_manager.connect returned False")
            return
        print("DEBUG: vc_manager.connect succeeded, activating session")
        
        session_manager.activate(session)
        print("DEBUG: Session activated, sending start message")
        
        await session_messenger.send_start_msg(session)
        print("DEBUG: Start message sent, playing alert")
        
        await player.alert(session)
        print("DEBUG: Alert played, resuming session")
        
        await resume(session)
        print("DEBUG: Session resumed successfully")
    except Exception as e:
        print(f"DEBUG: Exception in session_controller.start: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise


async def edit(session: Session, new_settings: Settings):
    short_break = new_settings.short_break or session.settings.short_break
    long_break = new_settings.long_break or session.settings.long_break
    intervals = new_settings.intervals or session.settings.intervals
    session.settings = Settings(new_settings.duration, short_break, long_break, intervals)
    await session_messenger.send_edit_msg(session)


async def end(session: Session):
    ctx = session.ctx
    await countdown.cleanup_pins(session)
    await session.auto_mute.unmute(ctx)
    if vc_accessor.get_voice_client(ctx):
        await vc_manager.disconnect(session)
    session_manager.deactivate(session)


async def run_interval(session: Session) -> bool:
    session.timer.running = True
    timer_end = session.timer.end
    await sleep(session.timer.remaining)
    s: Session | None = session_manager.active_sessions.get(session_manager.session_id_from(session.ctx))
    if not (s and
            s.timer.running and
            timer_end == s.timer.end):
        return False
    else:
        if await session_manager.kill_if_idle(session):
            return False
        if session.state == bot_enum.State.POMODORO:
            await session.auto_mute.unmute(session.ctx)
        await player.alert(session)
        await state_handler.transition(session)
    return True
