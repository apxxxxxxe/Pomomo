import time as t
from asyncio import sleep
import logging
import discord
from discord import Colour
import random

from . import session_manager, countdown, state_handler, pomodoro, session_messenger, classwork, goal_manager
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

    # 無限ループ防止のための安全装置
    max_iterations = 1000  # 最大反復回数
    iteration_count = 0

    while True:
        iteration_count += 1
        if iteration_count > max_iterations:
            logger.error(f"Session resume exceeded maximum iterations ({max_iterations}), terminating")
            break

        try:
            if not await run_interval(session):
                break
        except Exception as e:
            logger.error(f"Exception in run_interval: {e}")
            logger.exception("run_interval exception details:")
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

        # メッセージ送信
        await session_messenger.send_pomodoro_msg(session)
        logger.debug("Start message sent, playing alert")

        await player.alert(session)
        logger.debug("Alert played, resuming session")

        await resume(session)
        logger.info(f"Session resumed successfully for guild {session.ctx.guild.id}")
    except Exception as e:
        logger.error(f"Exception in session_controller.start_pomodoro: {type(e).__name__}: {e}")
        logger.exception("Exception details:")
        raise

async def start_classwork(session: Session):
    """
    classworkセッション開始処理
    """
    logger.info(f"Starting classwork session for guild {session.ctx.guild.id}")
    try:
        # 接続処理
        await classwork.handle_connection(session)
        await session_manager.activate(session)

        # メッセージ送信
        await session_messenger.send_classwork_msg(session)

        # 開始アラート音を再生
        await player.alert(session)

        await resume(session)
        logger.info(f"Classwork session started successfully for guild {session.ctx.guild.id}")
    except Exception as e:
        logger.error(f"Exception in session_controller.start_classwork: {type(e).__name__}: {e}")
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
    ctx = session.ctx
    logger.info(f"Ending session for guild {ctx.guild.id}")
    guild_id = ctx.guild.id

    # セッション終了時に該当ギルドの全ての目標と非対象ユーザーのリアクション記録を削除
    removed_goals = goal_manager.remove_all_goals_for_guild(guild_id)
    removed_reactions = goal_manager.remove_non_goal_user_reactions_for_guild(guild_id)
    if removed_goals > 0:
        logger.info(f"Removed {removed_goals} goals at session end for guild {guild_id}")
    if removed_reactions > 0:
        logger.info(f"Removed non-goal user reactions for {removed_reactions} users at session end for guild {guild_id}")

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

        # フェーズ終了時：既存のタイマーメッセージを削除
        if session.bot_start_msg:
            try:
                await session.bot_start_msg.delete()
                logger.debug("Deleted timer message before phase transition")
            except discord.errors.HTTPException as e:
                logger.warning(f"Failed to delete timer message: {e}")
            session.bot_start_msg = None

        if session.state == bot_enum.State.POMODORO:
            await session.auto_mute.unmute(session.ctx)
        elif session.state == bot_enum.State.CLASSWORK:
            await session.auto_mute.unmute(session.ctx)

        old_state = session.state
        await state_handler.transition(session)
        await player.alert(session)

        # フェーズ切り替え後：新しいタイマーメッセージを送信
        try:
            if session.state in [bot_enum.State.CLASSWORK, bot_enum.State.CLASSWORK_BREAK]:
                embed = msg_builder.settings_embed(session)
                timer_message = f'{random.choice(u_msg.ENCOURAGEMENTS)}'
                session.bot_start_msg = await session.ctx.channel.send(timer_message, embed=embed, silent=True)
            elif session.state in [bot_enum.State.POMODORO, bot_enum.State.SHORT_BREAK, bot_enum.State.LONG_BREAK]:
                embed = msg_builder.settings_embed(session)
                timer_message = f'{random.choice(u_msg.ENCOURAGEMENTS)}'
                session.bot_start_msg = await session.ctx.channel.send(timer_message, embed=embed, silent=True)
            logger.debug("Created new timer message after phase transition")
        except Exception as e:
            logger.error(f"Failed to create new timer message: {e}")

        # 作業フェーズ終了時の進捗確認処理
        if old_state in [bot_enum.State.POMODORO, bot_enum.State.CLASSWORK]:
            await _handle_progress_check(session)

    return True


async def _handle_progress_check(session: Session):
    """作業フェーズ終了時の進捗確認処理"""
    guild_id = session.ctx.guild.id
    work_duration_minutes = session.settings.duration

    # ギルドの作業回数を増加
    guild_count = goal_manager.increment_guild_work_count(guild_id)
    logger.debug(f"Guild {guild_id} work count after increment: {guild_count}")

    # 該当ギルドの全ての目標を取得
    goals = goal_manager.get_all_goals_for_guild(guild_id)

    # 進捗確認対象のユーザーを収集（ボイスチャンネル参加者のみ）
    users_to_check = []
    voice_channel = vc_accessor.get_voice_channel(session.ctx)

    for user_id, goal in goals.items():
        if goal_manager.should_check_progress(guild_id, user_id, work_duration_minutes):
            # ボイスチャンネルに参加しているかチェック
            if voice_channel:
                user_in_voice = any(member.id == user_id for member in voice_channel.members)
                if user_in_voice:
                    users_to_check.append((user_id, goal))
                else:
                    logger.debug(f"User {user_id} not in voice channel, skipping progress check")
            else:
                # ボイスチャンネルが取得できない場合はログ出力のみ
                logger.warning("Voice channel not found for progress check")

    # 対象ユーザーがいる場合のみメッセージを送信
    if users_to_check:
        try:
            # 各ユーザーの目標を含むembedを構築
            embed = discord.Embed(
                title="進捗確認（約1時間ごとに実施）",
                description="お疲れ様です。進み具合はいかがですか？",
                color=Colour.blue()
            )

            # 各ユーザーの目標をフィールドとして追加
            for user_id, goal in users_to_check:
                # ユーザーオブジェクトを取得して表示名を取得
                user = session.ctx.guild.get_member(user_id)
                user_display_name = user.display_name if user else f"User {user_id}"

                embed.add_field(
                    name=user_display_name,
                    value=f"`{goal}`",
                    inline=False
                )

            # リアクション説明をフッターに追加
            footer_text = "🏆:目標達成！ 😎:順調 👌:まあまあ 😇:だめ"
            embed.set_footer(text=footer_text)

            sent_message = await session.ctx.channel.send(embed=embed, silent=True)

            # リアクションを追加
            reactions = ["🏆", "😎", "👌", "😇"]
            for reaction in reactions:
                await sent_message.add_reaction(reaction)

            logger.info(f"Sent progress check to {len(users_to_check)} users in guild {guild_id}")

        except Exception as e:
            logger.error(f"Failed to send progress check message: {e}")
