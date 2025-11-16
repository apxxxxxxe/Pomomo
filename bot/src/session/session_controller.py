import time as t
from asyncio import sleep
import logging
import discord
from discord import Colour
import random

from . import session_manager, countdown, state_handler, pomodoro
from .Session import Session
from ..utils import player, msg_builder
from ..voice_client import vc_accessor, vc_manager
from configs import config, bot_enum, user_messages as u_msg
from configs.logging_config import get_logger

logger = get_logger(__name__)


async def resume(session: Session):
    logger.debug(f"Resuming session for guild {session.ctx.guild.id}")
    session.timeout = int(t.time() + config.TIMEOUT_SECONDS)
    await state_handler.auto_mute(session)
    if session.state == bot_enum.State.COUNTDOWN:
        await countdown.start(session)
        return
    while True:
        if not await run_interval(session):
            break


async def start_pomodoro(session: Session):
    # response.defer(ephemeral=True)の後に呼ばれる前提
    logger.info(f"Starting pomodoro session for guild {session.ctx.guild.id}")
    try:
        logger.debug("Calling vc_manager.connect")
        if not await vc_manager.connect(session):
            logger.warning("vc_manager.connect returned False")
            return
        logger.debug("vc_manager.connect succeeded, activating session")
        
        await session_manager.activate(session)
        logger.info(f"Session activated for guild {session.ctx.guild.id}")
        
        embed = msg_builder.settings_embed(session)
        message = f'> -# {session.ctx.user.display_name} さんが`/pomodoro`を使用しました\n{random.choice(u_msg.GREETINGS)}'
        # defer()によるthinkingメッセージを削除して、チャンネルに送信
        await session.ctx.delete_original_response()
        session.bot_start_msg = await session.ctx.channel.send(message, embed=embed, silent=True)
        
        # ピン留め処理（レート制限エラーをハンドリング）
        try:
            await session.bot_start_msg.pin()
        except discord.errors.HTTPException as e:
            if e.code == 40062:  # レート制限エラー
                logger.warning(f"Rate limited when pinning message: {e}")
                # ピン留めできなくても続行（機能的には問題ない）
            else:
                raise  # その他のエラーは再発生
        
        logger.debug("Start message sent, playing alert")
        
        await player.alert(session)
        logger.debug("Alert played, resuming session")
        
        await resume(session)
        logger.info(f"Session resumed successfully for guild {session.ctx.guild.id}")
    except Exception as e:
        logger.error(f"Exception in session_controller.start_pomodoro: {type(e).__name__}: {e}")
        logger.exception("Exception details:")
        raise


async def cleanup_pins(session: Session):
    """過去のセッションのピン留めメッセージをクリーンアップする。
    現在のセッションのbot_start_msgは処理から除外する。
    レート制限エラーの場合はスキップする。
    """
    try:
        pins = await session.ctx.channel.pins()
    except discord.errors.HTTPException as e:
        if e.code == 40062:  # レート制限エラー
            logger.warning(f"Rate limited when fetching pins: {e}")
            return  # クリーンアップをスキップ
        else:
            raise  # その他のエラーは再発生
    
    for pinned_msg in pins:
        # botが送信したピン留めメッセージで、現在のセッションのbot_start_msgではないもののみ処理
        bot_user = (session.ctx.client if hasattr(session.ctx, 'client') else session.ctx.bot).user
        is_bot_message = pinned_msg.author == bot_user
        is_not_current_session = not session.bot_start_msg or pinned_msg.id != session.bot_start_msg.id
        
        if is_bot_message and is_not_current_session:
            # 過去のセッションのピン留めメッセージをアンピンして削除
            try:
                await pinned_msg.unpin()
                await pinned_msg.delete()
                logger.info(f"Cleaned up old pinned message (ID: {pinned_msg.id})")
            except discord.errors.HTTPException as e:
                logger.error(f"Failed to cleanup old pinned message (ID: {pinned_msg.id}): {e}")
                # エラーが発生してもクリーンアップを続行
                continue


async def end(session: Session):
    logger.info(f"Ending session for guild {session.ctx.guild.id}")
    ctx = session.ctx
    await cleanup_pins(session)
    # mute モードでない場合のみ unmute を実行
    if not getattr(session, 'is_muted_mode', False):
        await session.auto_mute.unmute(ctx)
    if vc_accessor.get_voice_client(ctx):
        await vc_manager.disconnect(session)
    await session_manager.deactivate(session)


async def run_interval(session: Session) -> bool:
    logger.debug(f"Running interval for session in guild {session.ctx.guild.id}")
    import time
    
    session.timer.running = True
    session.timer.end = time.time() + session.timer.remaining
    timer_end = session.timer.end
    
    # セッション開始時刻を記録
    session.current_session_start_time = time.time()
    
    # Pomodoro及びClassworkセッション中の残り時間表示
    if session.state in [bot_enum.State.POMODORO, bot_enum.State.SHORT_BREAK, bot_enum.State.LONG_BREAK, bot_enum.State.CLASSWORK, bot_enum.State.CLASSWORK_BREAK]:
        last_remaining_seconds = -1  # 前回更新時の残り秒数を記録
        # タイマー開始時に1度表示を更新
        if session.state in [bot_enum.State.CLASSWORK, bot_enum.State.CLASSWORK_BREAK]:
            from . import classwork
            await classwork.update_msg(session)
        elif session.state in [bot_enum.State.POMODORO, bot_enum.State.SHORT_BREAK, bot_enum.State.LONG_BREAK]:
            await pomodoro.update_msg(session)
        while session.timer.remaining > 0:
            await sleep(1)
            s: Session | None = session_manager.active_sessions.get(session_manager.session_id_from(session.ctx))
            if not (s and
                    s.timer.running and
                    timer_end == s.timer.end):
                return False
            
            # タイマーの残り時間を更新
            session.timer.remaining = session.timer.end - time.time()
            
            # 残り時間に応じた更新判定
            remaining_seconds = round(session.timer.remaining)
            remaining_minutes = int(session.timer.remaining / 60)
            should_update = False
            
            if (remaining_minutes == session.settings.duration - 1 and (session.state in [bot_enum.State.POMODORO, bot_enum.State.CLASSWORK])) or remaining_seconds < 60:
                # 開始1分未満または残り時間1分未満の場合: 秒数の1の位が0か5のときのみ更新（0:55, 0:50, ..., 0:05, 0:00）
                should_update = remaining_seconds % 10 == 0 or remaining_seconds % 10 == 5
            else:
                # 1分以上の場合: 秒数が0または30のときのみ更新（1:00, 1:30, 2:00等）
                should_update = remaining_seconds % 60 == 0 or remaining_seconds % 60 == 30
            
            # 更新条件を満たし、かつ前回と異なる秒数の場合のみ更新
            if should_update and remaining_seconds != last_remaining_seconds:
                if session.state in [bot_enum.State.CLASSWORK, bot_enum.State.CLASSWORK_BREAK]:
                    from . import classwork
                    await classwork.update_msg(session)
                elif session.state in [bot_enum.State.POMODORO, bot_enum.State.SHORT_BREAK, bot_enum.State.LONG_BREAK]:
                    await pomodoro.update_msg(session)
                last_remaining_seconds = remaining_seconds
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
