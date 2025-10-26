import time as t
from asyncio import sleep
from discord import Colour
import random

from . import session_manager, countdown, state_handler, pomodoro
from .Session import Session
from ..utils import player, msg_builder
from ..voice_client import vc_accessor, vc_manager
from configs import config, bot_enum, user_messages as u_msg


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
    # response.defer(ephemeral=True)の後に呼ばれる前提
    print("DEBUG: session_controller.start called")
    try:
        print("DEBUG: Calling vc_manager.connect")
        if not await vc_manager.connect(session):
            print("DEBUG: vc_manager.connect returned False")
            return
        print("DEBUG: vc_manager.connect succeeded, activating session")
        
        session_manager.activate(session)
        print("DEBUG: Session activated, sending start message")
        
        embed = msg_builder.settings_embed(session)
        message = f'> -# {session.ctx.user.display_name} さんが`/start`を使用しました\n{random.choice(u_msg.GREETINGS)}'
        # defer()によるthinkingメッセージを削除して、チャンネルに送信
        await session.ctx.delete_original_response()
        session.bot_start_msg = await session.ctx.channel.send(message, embed=embed, silent=True)
        await session.bot_start_msg.pin()
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


async def cleanup_pins(session: Session):
    for pinned_msg in await session.ctx.channel.pins():
        # botが送信したピン留めメッセージをアンピンし、色を赤に変更
        if pinned_msg.author == (session.ctx.client if hasattr(session.ctx, 'client') else session.ctx.bot).user:
            embed = pinned_msg.embeds[0]
            embed.colour = Colour.red()
            await pinned_msg.unpin()
            await pinned_msg.edit(embed=embed)


async def end(session: Session):
    ctx = session.ctx
    await cleanup_pins(session)
    await session.auto_mute.unmute(ctx)
    if vc_accessor.get_voice_client(ctx):
        await vc_manager.disconnect(session)
    session_manager.deactivate(session)


async def run_interval(session: Session) -> bool:
    import time
    
    session.timer.running = True
    session.timer.end = time.time() + session.timer.remaining
    timer_end = session.timer.end
    
    # セッション開始時刻を記録
    session.current_session_start_time = time.time()
    
    # Pomodoro及びClassworkセッション中の残り時間表示
    if session.state in [bot_enum.State.POMODORO, bot_enum.State.SHORT_BREAK, bot_enum.State.LONG_BREAK, bot_enum.State.CLASSWORK, bot_enum.State.CLASSWORK_BREAK]:
        while session.timer.remaining > 0:
            await sleep(1)
            s: Session | None = session_manager.active_sessions.get(session_manager.session_id_from(session.ctx))
            if not (s and
                    s.timer.running and
                    timer_end == s.timer.end):
                return False
            if session.state in [bot_enum.State.CLASSWORK, bot_enum.State.CLASSWORK_BREAK]:
                from . import classwork
                await classwork.update_msg(session)
            else:
                await pomodoro.update_msg(session)
    else:
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
        elif session.state == bot_enum.State.CLASSWORK:
            await session.auto_mute.unmute(session.ctx)
        await state_handler.transition(session)
        await player.alert(session)
    return True
