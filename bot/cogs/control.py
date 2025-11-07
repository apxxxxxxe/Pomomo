import time as t

import discord
from discord.ext import commands
from discord import app_commands

from src.Settings import Settings
from configs import bot_enum, user_messages as u_msg, config
from src.session import session_manager, session_controller, session_messenger, countdown, state_handler, pomodoro, classwork
from src.session.Session import Session
from src.utils import player, msg_builder, voice_validation
from src.voice_client import vc_accessor


class Control(commands.Cog):

    def __init__(self, client):
        self.client = client


    @app_commands.command(name="pomodoro", description="ポモドーロセッションを開始する")
    @app_commands.describe(
        pomodoro="作業時間（分、デフォルト: 25）",
        short_break="短い休憩時間（分、デフォルト: 5）",
        long_break="長い休憩時間（分、デフォルト: 20）",
        intervals="長い休憩までの繰り返し数（デフォルト: 4）"
    )
    async def pomodoro(self, interaction: discord.Interaction, pomodoro: int = 25, short_break: int = 5, long_break: int = 20, intervals: int = 4):
        print(f"DEBUG: pomodoro command called with params: pomodoro={pomodoro}, short_break={short_break}, long_break={long_break}, intervals={intervals}")
        
        if not await Settings.is_valid_interaction(interaction, pomodoro, short_break, long_break, intervals):
            print("DEBUG: Settings.is_valid_interaction returned False")
            await interaction.response.send_message(u_msg.INVALID_DURATION_ERR.format(max_minutes=config.MAX_INTERVAL_MINUTES), ephemeral=True)
            return
            
        print("DEBUG: Settings validation passed")
        
        if session_manager.active_sessions.get(session_manager.session_id_from(interaction)):
            print("DEBUG: Active session exists")
            await interaction.response.send_message(u_msg.ACTIVE_SESSION_EXISTS_ERR, ephemeral=True)
            return
            
        print("DEBUG: No active session found")
        
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
            
        print("DEBUG: Voice permission check passed, creating session")

        # 時間のかかる処理開始前にdefer
        await interaction.response.defer(ephemeral=True)
        session = Session(bot_enum.State.POMODORO,
                          Settings(pomodoro, short_break, long_break, intervals),
                          interaction,
                          )
        print("DEBUG: Session created, starting session controller")
        try:
            await session_controller.start_pomodoro(session)
        except Exception as e:
            print(f"DEBUG: Error starting session: {e}")
            await interaction.delete_original_response()
            await interaction.channel.send(u_msg.POMODORO_START_FAILED)

    @pomodoro.error
    async def pomodoro_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        print(f"DEBUG: pomodoro_error triggered with error type: {type(error)}")
        print(f"DEBUG: error content: {error}")
        print(f"DEBUG: interaction.response.is_done(): {interaction.response.is_done()}")
        
        try:
            if isinstance(error, app_commands.CommandInvokeError):
                # システムエラーとして扱う
                if not interaction.response.is_done():
                    await interaction.response.send_message(u_msg.POMODORO_START_FAILED, ephemeral=True)
                else:
                    await interaction.followup.send(u_msg.POMODORO_START_FAILED, ephemeral=True)
            elif isinstance(error, app_commands.TransformError):
                # パラメータ変換エラー
                if not interaction.response.is_done():
                    await interaction.response.send_message(u_msg.INVALID_DURATION_ERR.format(max_minutes=config.MAX_INTERVAL_MINUTES), ephemeral=True)
                else:
                    await interaction.followup.send(u_msg.INVALID_DURATION_ERR.format(max_minutes=config.MAX_INTERVAL_MINUTES), ephemeral=True)
            else:
                # その他のエラー
                if not interaction.response.is_done():
                    await interaction.response.send_message(u_msg.POMODORO_START_FAILED, ephemeral=True)
                else:
                    await interaction.followup.send(u_msg.POMODORO_START_FAILED, ephemeral=True)
        except Exception as e:
            print(f"DEBUG: Error in pomodoro error handler: {e}")

    @app_commands.command(name="stop", description="現在のポモドーロセッションを停止する")
    async def stop(self, interaction: discord.Interaction):
        session = await session_manager.get_session_interaction(interaction)
        if not session:
            await interaction.response.send_message(u_msg.NO_SESSION_TO_STOP, ephemeral=True)
            return
            
        if not await voice_validation.require_same_voice_channel(interaction):
            guild = interaction.guild
            if guild and guild.voice_client:
                bot_name = interaction.client.user.display_name
                channel_name = guild.voice_client.channel.name
                await interaction.response.send_message(u_msg.SAME_VOICE_CHANNEL_REQUIRED_ERR.format(command="/stop", bot_name=bot_name, channel_name=channel_name), ephemeral=True)
            else:
                await interaction.response.send_message(u_msg.VOICE_CHANNEL_REQUIRED_ERR, ephemeral=True)
            return
        
        # 時間のかかる処理開始前にdefer
        await interaction.response.defer(ephemeral=True)
        
        try:
            print(f"DEBUG stop: session.state = {session.state}")
            print(f"DEBUG stop: session.current_session_start_time = {session.current_session_start_time}")
            print(f"DEBUG stop: session.stats.seconds_completed (before) = {session.stats.seconds_completed}")
            
            # セッション終了前に現在の経過時間を計算して統計に追加
            if session.current_session_start_time and (session.state == bot_enum.State.POMODORO or session.state == bot_enum.State.CLASSWORK):
                import time
                current_elapsed = int(time.time() - session.current_session_start_time)
                print(f"DEBUG stop: current_elapsed = {current_elapsed}")
                session.stats.seconds_completed += current_elapsed
                print(f"DEBUG stop: session.stats.seconds_completed (after) = {session.stats.seconds_completed}")
            else:
                print("DEBUG stop: Not adding current elapsed time")
                if not session.current_session_start_time:
                    print("DEBUG stop: current_session_start_time is None")
                if session.state != bot_enum.State.POMODORO and session.state != bot_enum.State.CLASSWORK:
                    print(f"DEBUG stop: state is not work state: {session.state}")
            
            await session_controller.end(session)

            # start_msgを条件に応じて書き換え
            if session.bot_start_msg:
                print("editing bot_start_msg...")
                embed = session.bot_start_msg.embeds[0]
                embed.description = f'終了'
                embed.set_footer(text='終了したセッション')
                message='またお会いしましょう！ 👋'
                embed.colour = discord.Colour.green()
                if (session.state == bot_enum.State.POMODORO or session.state == bot_enum.State.CLASSWORK):
                    message='お疲れ様です！ 👋'
                    embed.description = f'終了：{msg_builder.stats_msg(session.stats)}'
                await session.bot_start_msg.edit(content=message, embed=embed)
            
            # defer()によるthinkingメッセージを削除して、silent指定でチャンネルに送信
            await interaction.delete_original_response()
            await interaction.channel.send(f'> -# {interaction.user.display_name} さんが`/stop`を使用しました\nセッションを終了しました。', silent=True)
        except Exception as e:
            print(f"DEBUG: Error stopping session: {e}")
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
        print(f"DEBUG: countdown_error triggered with error type: {type(error)}")
        
        try:
            if isinstance(error, app_commands.CommandInvokeError):
                # システムエラーとして扱う
                if not interaction.response.is_done():
                    await interaction.response.send_message(u_msg.COUNTDOWN_START_FAILED, ephemeral=True)
                else:
                    await interaction.followup.send(u_msg.COUNTDOWN_START_FAILED, ephemeral=True)
            elif isinstance(error, app_commands.TransformError):
                # パラメータ変換エラー
                if not interaction.response.is_done():
                    await interaction.response.send_message(u_msg.INVALID_DURATION_ERR.format(max_minutes=180), ephemeral=True)
                else:
                    await interaction.followup.send(u_msg.INVALID_DURATION_ERR.format(max_minutes=180), ephemeral=True)
            else:
                # その他のエラー
                if not interaction.response.is_done():
                    await interaction.response.send_message(u_msg.COUNTDOWN_START_FAILED, ephemeral=True)
                else:
                    await interaction.followup.send(u_msg.COUNTDOWN_START_FAILED, ephemeral=True)
        except Exception as e:
            print(f"DEBUG: Error in countdown error handler: {e}")

    @app_commands.command(name="start", description="シンプルな作業タイマーを開始する")
    @app_commands.describe(
        work_time="作業時間（分、デフォルト: 30）",
        break_time="休憩時間（分、デフォルト: 30）"
    )
    async def classwork(self, interaction: discord.Interaction, work_time: int = 30, break_time: int = 30):
        if not await Settings.is_valid_interaction(interaction, work_time, break_time, 30, 4):
            await interaction.response.send_message(u_msg.INVALID_DURATION_ERR.format(max_minutes=config.MAX_INTERVAL_MINUTES), ephemeral=True)
            return
            
        if session_manager.active_sessions.get(session_manager.session_id_from(interaction)):
            await interaction.response.send_message(u_msg.ACTIVE_SESSION_EXISTS_ERR, ephemeral=True)
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
            
        # 時間のかかる処理開始前にdefer
        await interaction.response.defer(ephemeral=True)
        
        # CLASSWORKセッション作成（カスタム時間設定）
        # Settings(duration, short_break, long_break, intervals) の形式に合わせる
        session = Session(bot_enum.State.CLASSWORK,
                          Settings(work_time, break_time, 30, 1),  # classworkでは long_break, intervals は使わない
                          interaction,
                          )
        
        try:
            await classwork.handle_connection(session)
            session_manager.activate(session)
            await session_messenger.send_classwork_msg(session)
            
            # 開始アラート音を再生
            await player.alert(session)

            await session_controller.resume(session)
        except Exception as e:
            print(f"DEBUG: Error starting classwork session: {e}")
            await interaction.delete_original_response()
            await interaction.channel.send(u_msg.START_SESSION_FAILED)

    @classwork.error
    async def classwork_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        print(f"DEBUG: classwork_error triggered with error type: {type(error)}")
        
        try:
            if isinstance(error, app_commands.CommandInvokeError):
                # システムエラーとして扱う
                if not interaction.response.is_done():
                    await interaction.response.send_message(u_msg.START_SESSION_FAILED, ephemeral=True)
                else:
                    await interaction.followup.send(u_msg.START_SESSION_FAILED, ephemeral=True)
            elif isinstance(error, app_commands.TransformError):
                # パラメータ変換エラー
                if not interaction.response.is_done():
                    await interaction.response.send_message(u_msg.INVALID_DURATION_ERR.format(max_minutes=config.MAX_INTERVAL_MINUTES), ephemeral=True)
                else:
                    await interaction.followup.send(u_msg.INVALID_DURATION_ERR.format(max_minutes=config.MAX_INTERVAL_MINUTES), ephemeral=True)
            else:
                # その他のエラー
                if not interaction.response.is_done():
                    await interaction.response.send_message(u_msg.START_SESSION_FAILED, ephemeral=True)
                else:
                    await interaction.followup.send(u_msg.START_SESSION_FAILED, ephemeral=True)
        except Exception as e:
            print(f"DEBUG: Error in classwork error handler: {e}")


async def setup(client):
    await client.add_cog(Control(client))
