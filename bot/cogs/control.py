import time as t

import discord
from discord.ext import commands
from discord import app_commands

from src.Settings import Settings
from configs import config, bot_enum, user_messages as u_msg
from src.session import session_manager, session_controller, session_messenger, countdown, state_handler
from src.session.Session import Session
from src.utils import msg_builder


class Control(commands.Cog):

    def __init__(self, client):
        self.client = client

    @app_commands.command(name="start", description="Start a Pomodoro session")
    @app_commands.describe(
        pomodoro="作業時間（分、デフォルト: 20）",
        short_break="短い休憩時間（分、デフォルト: 5）",
        long_break="長い休憩時間（分、デフォルト: 15）",
        intervals="長い休憩までの繰り返し数（デフォルト: 4）"
    )
    async def start(self, interaction: discord.Interaction, pomodoro: int = 20, short_break: int = 5, long_break: int = 15, intervals: int = 4):
        print(f"DEBUG: start command called with params: pomodoro={pomodoro}, short_break={short_break}, long_break={long_break}, intervals={intervals}")
        
        if not await Settings.is_valid_interaction(interaction, pomodoro, short_break, long_break, intervals):
            print("DEBUG: Settings.is_valid_interaction returned False")
            return
            
        print("DEBUG: Settings validation passed")
        
        if session_manager.active_sessions.get(session_manager.session_id_from(interaction)):
            print("DEBUG: Active session exists")
            await interaction.response.send_message(u_msg.ACTIVE_SESSION_EXISTS_ERR)
            return
            
        print("DEBUG: No active session found")
        
        if not interaction.user.voice:
            print("DEBUG: User not in voice channel")
            await interaction.response.send_message('Pomomoを使用するには音声チャンネルに参加してください！')
            return

        # Voice channel validation
        user_vc = interaction.user.voice.channel
        tc = interaction.channel
        if user_vc.name != tc.name:
            await interaction.response.send_message(f'/start コマンドはテキストチャンネル{user_vc.name}で実行してください')
            return
            
        print("DEBUG: User in voice channel, creating session")

        session = Session(bot_enum.State.POMODORO,
                          Settings(pomodoro, short_break, long_break, intervals),
                          interaction)
        print("DEBUG: Session created, starting session controller")
        await session_controller.start(session)

    @start.error
    async def start_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        print(f"DEBUG: start_error triggered with error type: {type(error)}")
        print(f"DEBUG: error content: {error}")
        print(f"DEBUG: interaction.response.is_done(): {interaction.response.is_done()}")
        
        if isinstance(error, app_commands.CommandInvokeError):
            print("DEBUG: CommandInvokeError detected")
            if not interaction.response.is_done():
                print("DEBUG: Sending start_error_1 message")
                await interaction.response.send_message("start_error_1:" + u_msg.NUM_OUTSIDE_ONE_AND_MAX_INTERVAL_ERR, ephemeral=True)
            else:
                print("DEBUG: Sending start_error_2 followup message")
                await interaction.followup.send("start_error_2:" + u_msg.NUM_OUTSIDE_ONE_AND_MAX_INTERVAL_ERR, ephemeral=True)
        else:
            print(f"DEBUG: Other error type: {type(error)}")
            print(error)

    @app_commands.command(name="stop", description="Stop the current Pomodoro session")
    async def stop(self, interaction: discord.Interaction):
        session = await session_manager.get_session_interaction(interaction)
        if session:
            # Voice channel validation
            from src.voice_client import vc_accessor
            session_vc = vc_accessor.get_voice_channel(session.ctx)
            tc = interaction.channel
            if session_vc and session_vc.name != tc.name:
                await interaction.response.send_message(f'/stop コマンドはテキストチャンネル{session_vc.name}で実行してください')
                return

            if session.stats.pomos_completed > 0:
                await interaction.response.send_message(f'お疲れ様です！ {msg_builder.stats_msg(session.stats)}を完了しました。')
            else:
                await interaction.response.send_message(f'またお会いしましょう！ 👋')
            await session_controller.end(session)
        else:
            await interaction.response.send_message('停止するアクティブなセッションがありません。')

    @app_commands.command(name="skip", description="Skip the current interval")
    async def skip(self, interaction: discord.Interaction):
        session = await session_manager.get_session_interaction(interaction)
        if session:
            # Voice channel validation
            from src.voice_client import vc_accessor
            session_vc = vc_accessor.get_voice_channel(session.ctx)
            tc = interaction.channel
            if session_vc and session_vc.name != tc.name:
                await interaction.response.send_message(f'/skip コマンドはテキストチャンネル{session_vc.name}で実行してください')
                return

            if session.state == bot_enum.State.COUNTDOWN:
                await interaction.response.send_message(f'カウントダウンはスキップできません。終了するには/stop、やり直すには/restartを使用してください。')
                return
                
            stats = session.stats
            if stats.pomos_completed >= 0 and \
                    session.state == bot_enum.State.POMODORO:
                stats.pomos_completed -= 1
                stats.minutes_completed -= session.settings.duration

            await interaction.response.send_message(f'{session.state}をスキップします。')
            await state_handler.transition(session)
            await session_controller.resume(session)
        else:
            await interaction.response.send_message('スキップするセッションがありません。')

    @app_commands.command(name="countdown", description="Start a countdown timer")
    @app_commands.describe(
        duration="継続時間（分、1-180）",
        title="カウントダウンのタイトル（デフォルト: 'Countdown'）",
        audio_alert="音声アラート設定（省略可）"
    )
    async def countdown(self, interaction: discord.Interaction, duration: int, title: str = 'Countdown', audio_alert: str = None):
        session = session_manager.active_sessions.get(session_manager.session_id_from(interaction))
        if session:
            await interaction.response.send_message('アクティブなセッションが実行中です。カウントダウンを開始する前に、まず停止してください。')
            return

        if not 0 < duration <= 180:
            await interaction.response.send_message("countdown:" + u_msg.NUM_OUTSIDE_ONE_AND_MAX_INTERVAL_ERR)
            return

        if not interaction.user.voice:
            await interaction.response.send_message('Pomomoを使用するには音声チャンネルに参加してください！')
            return

        # Voice channel validation
        user_vc = interaction.user.voice.channel
        tc = interaction.channel
        if user_vc.name != tc.name:
            await interaction.response.send_message(f'/countdown コマンドはテキストチャンネル{user_vc.name}で実行してください')
            return
            
        session = Session(bot_enum.State.COUNTDOWN,
                          Settings(duration),
                          interaction)
        await countdown.handle_connection(session, audio_alert)
        session_manager.activate(session)
        await session_messenger.send_countdown_msg(session, title)
        await countdown.start(session)

    @countdown.error
    async def countdown_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandInvokeError):
            await interaction.followup.send("countdown_error: " + u_msg.NUM_OUTSIDE_ONE_AND_MAX_INTERVAL_ERR)
        else:
            print(error)


async def setup(client):
    await client.add_cog(Control(client))
