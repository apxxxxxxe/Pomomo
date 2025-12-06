import time as t
import logging
import asyncio

import discord
from discord.ext import commands
from discord import app_commands

from src.Settings import Settings
from configs import bot_enum, user_messages as u_msg, config
from configs.logging_config import get_logger
from src.session import session_manager, session_controller, session_messenger, countdown, state_handler, pomodoro, classwork
from src.session.Session import Session
from src.utils import player, msg_builder, voice_validation
from src.voice_client import vc_accessor

logger = get_logger(__name__)

# ギルドごとのコマンド実行のロック（コマンド別）
pomodoro_locks = {}
stop_locks = {}
start_locks = {}


class Control(commands.Cog):

    def __init__(self, client):
        self.client = client

    async def _validate_and_setup_session(self, interaction: discord.Interaction, command_name: str, lock_dict: dict) -> tuple[bool, str]:
        """
        共通の検証ロジックを実行し、セッション作成の準備を行う
        Returns: (is_valid, guild_id)
        """
        guild_id = str(interaction.guild.id)
        
        # ギルドごとのロックを取得または作成
        if guild_id not in lock_dict:
            lock_dict[guild_id] = asyncio.Lock()
        
        # ロックが既に取得されているかチェック
        if lock_dict[guild_id].locked():
            logger.warning(f"{command_name} command already running for guild {guild_id}")
            await interaction.response.send_message(u_msg.COMMAND_ALREADY_RUNNING.format(command=command_name), ephemeral=True)
            return False, guild_id
            
        return True, guild_id

    async def _validate_session_prerequisites(self, interaction: discord.Interaction) -> bool:
        """
        セッション開始前の前提条件を検証する
        Returns: True if all prerequisites are met
        """
        # アクティブセッションの確認
        if session_manager.active_sessions.get(session_manager.session_id_from(interaction)):
            await interaction.response.send_message(u_msg.ACTIVE_SESSION_EXISTS_ERR, ephemeral=True)
            return False
            
        # ユーザーがボイスチャンネルに参加しているかチェック
        if not interaction.user.voice:
            await interaction.response.send_message(u_msg.VOICE_CHANNEL_REQUIRED_ERR, ephemeral=True)
            return False
        
        # ボットの権限チェック
        voice_channel = interaction.user.voice.channel
        bot_member = interaction.guild.me
        
        if not voice_channel.permissions_for(bot_member).connect:
            await interaction.response.send_message(u_msg.BOT_CONNECT_PERMISSION_ERR.format(channel_name=voice_channel.name), ephemeral=True)
            return False
        
        if not voice_channel.permissions_for(bot_member).speak:
            await interaction.response.send_message(u_msg.BOT_SPEAK_PERMISSION_ERR.format(channel_name=voice_channel.name), ephemeral=True)
            return False
            
        return True

    async def _handle_session_start_error(self, interaction: discord.Interaction, session: Session, error: Exception, error_message: str):
        """
        セッション開始時のエラーを統一的に処理する
        """
        if isinstance(error, discord.errors.HTTPException):
            if error.code == 40062:  # レート制限エラー
                logger.warning(f"Rate limited during session start: {error}")
                await interaction.delete_original_response()
                await interaction.channel.send("レート制限に達しています。しばらくPomomoを休ませてあげましょう🍅")
                # セッションのクリーンアップ
                if session in session_manager.active_sessions.values():
                    await session_manager.deactivate(session)
                return
            else:
                logger.error(f"HTTPException starting session for guild {interaction.guild.id}: {error}")
                logger.exception("Exception details:")
        else:
            logger.error(f"Error starting session for guild {interaction.guild.id}: {error}")
            logger.exception("Exception details:")
            
        await interaction.delete_original_response()
        await interaction.channel.send(error_message)

    async def _handle_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError, start_failed_msg: str, command_name: str):
        """
        コマンドエラーを統一的に処理する
        """
        logger.error(f"{command_name} command error for user {interaction.user}: {type(error).__name__}")
        
        try:
            if isinstance(error, app_commands.CommandInvokeError):
                logger.exception(f"CommandInvokeError in {command_name} command:", exc_info=error)
                # システムエラーとして扱う
                if not interaction.response.is_done():
                    await interaction.response.send_message(start_failed_msg, ephemeral=True)
                else:
                    await interaction.followup.send(start_failed_msg, ephemeral=True)
            elif isinstance(error, app_commands.TransformError):
                logger.warning(f"TransformError in {command_name} command: {error}")
                # パラメータ変換エラー
                if not interaction.response.is_done():
                    await interaction.response.send_message(u_msg.INVALID_DURATION_ERR.format(max_minutes=config.MAX_INTERVAL_MINUTES), ephemeral=True)
                else:
                    await interaction.followup.send(u_msg.INVALID_DURATION_ERR.format(max_minutes=config.MAX_INTERVAL_MINUTES), ephemeral=True)
            else:
                logger.error(f"Unhandled error type in {command_name}: {type(error).__name__}")
                logger.exception("Exception details:", exc_info=error)
                # その他のエラー
                if not interaction.response.is_done():
                    await interaction.response.send_message(start_failed_msg, ephemeral=True)
                else:
                    await interaction.followup.send(start_failed_msg, ephemeral=True)
        except Exception as e:
            logger.error(f"Error in {command_name} error handler: {e}")
            logger.exception("Exception details:")


    @app_commands.command(name="pomodoro", description="ポモドーロセッションを開始する")
    @app_commands.describe(
        pomodoro="作業時間（分、デフォルト: 25）",
        short_break="短い休憩時間（分、デフォルト: 5）",
        long_break="長い休憩時間（分、デフォルト: 20）",
        intervals="長い休憩までの繰り返し数（デフォルト: 4）"
    )
    async def pomodoro(self, interaction: discord.Interaction, pomodoro: int = 25, short_break: int = 5, long_break: int = 20, intervals: int = 4):
        logger.info(f"Pomodoro command called by {interaction.user} with params: pomodoro={pomodoro}, short_break={short_break}, long_break={long_break}, intervals={intervals}")
        
        # 共通の検証ロジック
        is_valid, guild_id = await self._validate_and_setup_session(interaction, "/pomodoro", pomodoro_locks)
        if not is_valid:
            return
        
        async with pomodoro_locks[guild_id]:
            # 設定値検証
            if not await Settings.is_valid_interaction(interaction, pomodoro, short_break, long_break, intervals):
                logger.warning(f"Invalid settings provided by {interaction.user}")
                await interaction.response.send_message(u_msg.INVALID_DURATION_ERR.format(max_minutes=config.MAX_INTERVAL_MINUTES), ephemeral=True)
                return
                
            logger.debug("Settings validation passed")
            
            # セッション開始前の前提条件検証
            if not await self._validate_session_prerequisites(interaction):
                return
                
            logger.debug("Voice permission check passed, creating session")

            # 時間のかかる処理開始前にdefer
            await interaction.response.defer(ephemeral=True)
            session = Session(bot_enum.State.POMODORO,
                              Settings(pomodoro, short_break, long_break, intervals),
                              interaction,
                              )
            logger.info(f"Session created for guild {interaction.guild.id}, starting session controller")
            try:
                await session_controller.start_pomodoro(session)
            except Exception as e:
                await self._handle_session_start_error(interaction, session, e, u_msg.POMODORO_START_FAILED)

    @pomodoro.error
    async def pomodoro_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self._handle_command_error(interaction, error, u_msg.POMODORO_START_FAILED, "pomodoro")

    @app_commands.command(name="stop", description="現在のポモドーロセッションを停止する")
    async def stop(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        
        # ギルドごとのロックを取得または作成
        if guild_id not in stop_locks:
            stop_locks[guild_id] = asyncio.Lock()
        
        # ロックが既に取得されているかチェック
        if stop_locks[guild_id].locked():
            logger.warning(f"Stop command already running for guild {guild_id}")
            await interaction.response.send_message(u_msg.COMMAND_ALREADY_RUNNING.format(command="/stop"), ephemeral=True)
            return
        
        async with stop_locks[guild_id]:
            # 最初にdeferを呼ぶ（3秒以内のタイムアウトを防ぐため）
            await interaction.response.defer(ephemeral=True)
            
            session = await session_manager.get_session_interaction(interaction)
            if not session:
                await interaction.followup.send(u_msg.NO_SESSION_TO_STOP, ephemeral=True)
                return
                
            if not await voice_validation.require_same_voice_channel(interaction):
                guild = interaction.guild
                if guild and guild.voice_client:
                    bot_name = interaction.client.user.display_name
                    channel_name = guild.voice_client.channel.name
                    await interaction.followup.send(u_msg.SAME_VOICE_CHANNEL_REQUIRED_ERR.format(command="/stop", bot_name=bot_name, channel_name=channel_name), ephemeral=True)
                else:
                    await interaction.followup.send(u_msg.VOICE_CHANNEL_REQUIRED_ERR, ephemeral=True)
                return
            
            try:
                logger.debug(f"Stop command: session.state = {session.state}")
                logger.debug(f"Stop command: session.current_session_start_time = {session.current_session_start_time}")
                logger.debug(f"Stop command: session.stats.seconds_completed (before) = {session.stats.seconds_completed}")
                
                # セッション終了前に現在の経過時間を計算して統計に追加
                if session.current_session_start_time and (session.state == bot_enum.State.POMODORO or session.state == bot_enum.State.CLASSWORK):
                    import time
                    current_elapsed = int(time.time() - session.current_session_start_time)
                    logger.debug(f"Stop command: current_elapsed = {current_elapsed}")
                    session.stats.seconds_completed += current_elapsed
                    logger.debug(f"Stop command: session.stats.seconds_completed (after) = {session.stats.seconds_completed}")
                else:
                    logger.debug("Stop command: Not adding current elapsed time")
                    if not session.current_session_start_time:
                        logger.debug("Stop command: current_session_start_time is None")
                    if session.state != bot_enum.State.POMODORO and session.state != bot_enum.State.CLASSWORK:
                        logger.debug(f"Stop command: state is not work state: {session.state}")
                
                try:
                    await session_controller.end(session)
                except discord.errors.HTTPException as e:
                    if e.code == 40062:  # レート制限エラー
                        logger.warning(f"Rate limited during session stop: {e}")
                        # レート制限でもセッションは終了させる
                        await session_manager.deactivate(session)
                        await interaction.followup.send("レート制限に達しています。しばらくPomomoを休ませてあげましょう🍅\n（セッションは終了しました）")
                        return
                    else:
                        raise  # その他のHTTPエラーは再発生

                # start_msgを削除して新しいメッセージを投稿
                if session.bot_start_msg:
                    logger.debug("Replacing bot start message with completion message")
                    
                    # 新しいembedを作成
                    if session.bot_start_msg.embeds:
                        embed = session.bot_start_msg.embeds[0].copy()
                        embed.description = f'終了：{msg_builder.stats_msg(session.stats)}'
                        embed.set_footer(text='終了したセッション')
                        embed.colour = discord.Colour.green()
                        if session.stats.seconds_completed > 0:
                            message='お疲れ様です！ 👋'
                        else:
                            message='またお会いしましょう！ 👋'
                        
                        # 古いメッセージを削除
                        try:
                            await session.bot_start_msg.delete()
                            # ユーザー情報を含めた新しいメッセージとして投稿
                            stop_info = f'> -# {interaction.user.display_name} さんが`/stop`を使用しました\n'
                            await session.ctx.channel.send(content=stop_info + message, embed=embed)
                            logger.info(f"Replaced start message with completion message")
                        except discord.errors.HTTPException as e:
                            logger.error(f"Failed to delete/replace start message: {e}")
                            # 削除に失敗した場合は、編集を試みる（フォールバック）
                            try:
                                stop_info = f'> -# {interaction.user.display_name} さんが`/stop`を使用しました\n'
                                await session.bot_start_msg.edit(content=stop_info + message, embed=embed)
                            except discord.errors.HTTPException:
                                logger.warning(f"Cannot edit or delete start message. Continuing...")
                
                # defer()によるthinkingメッセージを削除
                await interaction.delete_original_response()
            except Exception as e:
                logger.error(f"Error stopping session: {e}")
                logger.exception("Exception details:")
                await interaction.delete_original_response()
                await interaction.channel.send(u_msg.SESSION_STOP_FAILED, silent=True)

    @app_commands.command(name="skip", description="現在のインターバルをスキップする")
    async def skip(self, interaction: discord.Interaction):
        session = await session_manager.get_session_interaction(interaction)
        if session:
            if not await voice_validation.require_same_voice_channel(interaction):
                guild = interaction.guild
                if guild and guild.voice_client:
                    bot_name = interaction.client.user.display_name
                    channel_name = guild.voice_client.channel.name
                    await interaction.response.send_message(u_msg.SAME_VOICE_CHANNEL_REQUIRED_ERR.format(command="/skip", bot_name=bot_name, channel_name=channel_name), ephemeral=True)
                else:
                    await interaction.response.send_message(u_msg.VOICE_CHANNEL_REQUIRED_ERR, ephemeral=True)
                return
            
            if session.state == bot_enum.State.COUNTDOWN:
                await interaction.response.send_message(u_msg.COUNTDOWN_SKIP_NOT_ALLOWED, ephemeral=True)
                return
                
            stats = session.stats
            if stats.pomos_completed >= 0 and \
                    session.state == bot_enum.State.POMODORO:
                stats.pomos_completed -= 1
                stats.seconds_completed -= session.settings.duration * 60

            old_state = session.state
            await state_handler.transition(session)
            await interaction.response.send_message(f'{bot_enum.State.get_display_name(old_state)}をスキップし、{bot_enum.State.get_display_name(session.state)}を開始します。')
            await player.alert(session)
            await session_controller.resume(session)
        else:
            await interaction.response.send_message(u_msg.NO_SESSION_TO_SKIP, ephemeral=True)

    @app_commands.command(name="countdown", description="カウントダウンタイマーを開始する")
    @app_commands.describe(
        duration="継続時間（分、1-180）",
        title="カウントダウンのタイトル（デフォルト: 'Countdown'）",
        audio_alert="音声アラート設定（省略可）"
    )
    async def countdown(self, interaction: discord.Interaction, duration: int, title: str = 'Countdown', audio_alert: str = None):
        session = session_manager.active_sessions.get(session_manager.session_id_from(interaction))
        if session:
            session_vc = vc_accessor.get_voice_channel(session.ctx)
            await interaction.response.send_message(u_msg.ACTIVE_SESSION_IN_CHANNEL.format(channel_name=session_vc.name), ephemeral=True)
            return

        if not 0 < duration <= 180:
            await interaction.response.send_message(u_msg.INVALID_DURATION_ERR.format(max_minutes=180), ephemeral=True)
            return

        # ユーザーがボイスチャンネルに参加しているかチェック
        if not interaction.user.voice:
            await interaction.response.send_message(u_msg.VOICE_CHANNEL_REQUIRED_ERR, ephemeral=True)
            return
        
        # ボットの権限チェック
        voice_channel = interaction.user.voice.channel
        bot_member = interaction.guild.me
        
        if not voice_channel.permissions_for(bot_member).connect:
            await interaction.response.send_message(u_msg.BOT_CONNECT_PERMISSION_ERR.format(channel_name=voice_channel.name), ephemeral=True)
            return
        
        if not voice_channel.permissions_for(bot_member).speak:
            await interaction.response.send_message(u_msg.BOT_SPEAK_PERMISSION_ERR.format(channel_name=voice_channel.name), ephemeral=True)
            return
            
        session = Session(bot_enum.State.COUNTDOWN,
                          Settings(duration),
                          interaction,
                          )
        await countdown.handle_connection(session, audio_alert)
        session_manager.activate(session)
        await session_messenger.send_countdown_msg(session, title)
        await countdown.start(session)

    @countdown.error
    async def countdown_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        logger.error(f"Countdown command error for user {interaction.user}: {type(error).__name__}")
        
        try:
            if isinstance(error, app_commands.CommandInvokeError):
                logger.exception("CommandInvokeError in countdown command:", exc_info=error)
                # システムエラーとして扱う
                if not interaction.response.is_done():
                    await interaction.response.send_message(u_msg.COUNTDOWN_START_FAILED, ephemeral=True)
                else:
                    await interaction.followup.send(u_msg.COUNTDOWN_START_FAILED, ephemeral=True)
            elif isinstance(error, app_commands.TransformError):
                logger.warning(f"TransformError in countdown command: {error}")
                # パラメータ変換エラー
                if not interaction.response.is_done():
                    await interaction.response.send_message(u_msg.INVALID_DURATION_ERR.format(max_minutes=180), ephemeral=True)
                else:
                    await interaction.followup.send(u_msg.INVALID_DURATION_ERR.format(max_minutes=180), ephemeral=True)
            else:
                logger.error(f"Unhandled error type in countdown: {type(error).__name__}")
                logger.exception("Exception details:", exc_info=error)
                # その他のエラー
                if not interaction.response.is_done():
                    await interaction.response.send_message(u_msg.COUNTDOWN_START_FAILED, ephemeral=True)
                else:
                    await interaction.followup.send(u_msg.COUNTDOWN_START_FAILED, ephemeral=True)
        except Exception as e:
            logger.error(f"Error in countdown error handler: {e}")
            logger.exception("Exception details:")

    @app_commands.command(name="start", description="シンプルな作業タイマーを開始する")
    @app_commands.describe(
        work_time="作業時間（分、デフォルト: 30）",
        break_time="休憩時間（分、デフォルト: 30）"
    )
    async def classwork(self, interaction: discord.Interaction, work_time: int = 30, break_time: int = 30):
        logger.info(f"Start command called by {interaction.user} with params: work_time={work_time}, break_time={break_time}")
        
        # 共通の検証ロジック
        is_valid, guild_id = await self._validate_and_setup_session(interaction, "/start", start_locks)
        if not is_valid:
            return
        
        async with start_locks[guild_id]:
            # 設定値検証
            if not await Settings.is_valid_interaction(interaction, work_time, break_time, 30, 4):
                await interaction.response.send_message(u_msg.INVALID_DURATION_ERR.format(max_minutes=config.MAX_INTERVAL_MINUTES), ephemeral=True)
                return
                
            logger.debug("Settings validation passed")
            
            # セッション開始前の前提条件検証
            if not await self._validate_session_prerequisites(interaction):
                return
                
            logger.debug("Voice permission check passed, creating session")

            # 時間のかかる処理開始前にdefer
            await interaction.response.defer(ephemeral=True)
            
            # CLASSWORKセッション作成（カスタム時間設定）
            session = Session(bot_enum.State.CLASSWORK,
                              Settings(work_time, break_time, 30, 1),  # classworkでは long_break, intervals は使わない
                              interaction,
                              )
            logger.info(f"Session created for guild {interaction.guild.id}, starting session controller")
            
            try:
                await session_controller.start_classwork(session)
            except Exception as e:
                await self._handle_session_start_error(interaction, session, e, u_msg.START_SESSION_FAILED)

    @classwork.error
    async def classwork_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self._handle_command_error(interaction, error, u_msg.START_SESSION_FAILED, "classwork")


async def setup(client):
    await client.add_cog(Control(client))
