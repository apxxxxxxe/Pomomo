import time as t

import discord
from discord.ext import commands
from discord import app_commands

from src.Settings import Settings
from configs import config, bot_enum, user_messages as u_msg
from src.session import session_manager, session_controller, session_messenger, countdown, state_handler, pomodoro
from src.session.Session import Session
from src.utils import player, msg_builder, voice_validation
from src.voice_client import vc_accessor


class Control(commands.Cog):

    def __init__(self, client):
        self.client = client


    @app_commands.command(name="start", description="ポモドーロセッションを開始する")
    @app_commands.describe(
        pomodoro="作業時間（分、デフォルト: 30）",
        short_break="短い休憩時間（分、デフォルト: 30）",
        long_break="長い休憩時間（分、デフォルト: 45）",
        intervals="長い休憩までの繰り返し数（デフォルト: 4）"
    )
    async def start(self, interaction: discord.Interaction, pomodoro: int = 30, short_break: int = 30, long_break: int = 45, intervals: int = 4):
        print(f"DEBUG: start command called with params: pomodoro={pomodoro}, short_break={short_break}, long_break={long_break}, intervals={intervals}")
        
        # 即座にdeferでレスポンス
        await interaction.response.defer()
        
        if not await Settings.is_valid_interaction(interaction, pomodoro, short_break, long_break, intervals):
            print("DEBUG: Settings.is_valid_interaction returned False")
            await interaction.followup.send("無効なパラメータです。", ephemeral=True)
            return
            
        print("DEBUG: Settings validation passed")
        
        if session_manager.active_sessions.get(session_manager.session_id_from(interaction)):
            print("DEBUG: Active session exists")
            await interaction.followup.send(u_msg.ACTIVE_SESSION_EXISTS_ERR, ephemeral=True)
            return
            
        print("DEBUG: No active session found")
        
        if not await voice_validation.require_voice_channel(interaction):
            print("DEBUG: User not in voice channel")
            await interaction.followup.send('`/start` コマンドはボイスチャンネルに参加してから実行してください', ephemeral=True)
            return
            
        print("DEBUG: User in voice channel, creating session")

        session = Session(bot_enum.State.POMODORO,
                          Settings(pomodoro, short_break, long_break, intervals),
                          interaction,
                          )
        print("DEBUG: Session created, starting session controller")
        try:
            await session_controller.start(session)
        except Exception as e:
            print(f"DEBUG: Error starting session: {e}")
            await interaction.followup.send("セッションの開始に失敗しました。", ephemeral=True)

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

    @app_commands.command(name="stop", description="現在のポモドーロセッションを停止する")
    async def stop(self, interaction: discord.Interaction):
        # 即座にdeferでレスポンス
        await interaction.response.defer()
        session = await session_manager.get_session_interaction(interaction)
        if session:
            if not await voice_validation.require_same_voice_channel(interaction):
                guild = interaction.guild
                if guild and guild.voice_client:
                    bot_name = interaction.client.user.display_name
                    channel_name = guild.voice_client.channel.name
                    await interaction.followup.send(f'`/stop` コマンドは `{bot_name}` と同じボイスチャンネル `{channel_name}` に参加してから実行してください', ephemeral=True)
                else:
                    await interaction.followup.send('`/stop` コマンドはボイスチャンネルに参加してから実行してください', ephemeral=True)
                return
            
            try:
                await session_controller.end(session)

                # start_msgを条件に応じて書き換え
                if session.bot_start_msg:
                    print("editing bot_start_msg...")
                    embed = session.bot_start_msg.embeds[0]
                    embed.set_footer(text='終了したセッション')
                    message='またお会いしましょう！ 👋'
                    if session.state == bot_enum.State.POMODORO and session.stats.pomos_completed >= 1:
                        message='お疲れ様です！ 👋'
                        embed.description = f'終了：{msg_builder.stats_msg(session.stats)}'
                        embed.colour = discord.Colour.green()
                    else:
                        embed.description = '中断'
                        embed.colour = discord.Colour.red()
                    await session.bot_start_msg.edit(content=message, embed=embed)
                
                await interaction.followup.send('セッションを終了しました。', silent=True)
            except Exception as e:
                print(f"DEBUG: Error stopping session: {e}")
                await interaction.followup.send('セッション終了時にエラーが発生しました。', ephemeral=True)
        else:
            await interaction.followup.send('停止するアクティブなセッションがありません。', ephemeral=True)

    @app_commands.command(name="skip", description="現在のインターバルをスキップする")
    async def skip(self, interaction: discord.Interaction):
        session = await session_manager.get_session_interaction(interaction)
        if session:
            if not await voice_validation.require_same_voice_channel(interaction):
                guild = interaction.guild
                if guild and guild.voice_client:
                    bot_name = interaction.client.user.display_name
                    channel_name = guild.voice_client.channel.name
                    await interaction.response.send_message(f'`/skip` コマンドは `{bot_name}` と同じボイスチャンネル `{channel_name}` に参加してから実行してください', ephemeral=True)
                else:
                    await interaction.response.send_message('`/skip` コマンドはボイスチャンネルに参加してから実行してください', ephemeral=True)
                return
            
            if session.state == bot_enum.State.COUNTDOWN:
                await interaction.response.send_message(f'カウントダウンはスキップできません。終了するには`/stop`を使用してください。', ephemeral=True)
                return
                
            stats = session.stats
            if stats.pomos_completed >= 0 and \
                    session.state == bot_enum.State.POMODORO:
                stats.pomos_completed -= 1
                stats.minutes_completed -= session.settings.duration

            old_state = session.state
            await state_handler.transition(session)
            await interaction.response.send_message(f'{old_state}をスキップし、{session.state}を開始します。')
            await player.alert(session)
            await session_controller.resume(session)
        else:
            await interaction.response.send_message('スキップするセッションがありません。', ephemeral=True)

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
            await interaction.response.send_message(f'アクティブなセッションが{session_vc.name}で実行中です。\nカウントダウンを開始する前に、まず停止してください。', ephemeral=True)
            return

        if not 0 < duration <= 180:
            await interaction.response.send_message("countdown:" + u_msg.NUM_OUTSIDE_ONE_AND_MAX_INTERVAL_ERR, ephemeral=True)
            return

        if not await voice_validation.require_voice_channel(interaction):
            await interaction.response.send_message('`/countdown` コマンドはボイスチャンネルに参加してから実行してください', ephemeral=True)
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
        if isinstance(error, app_commands.CommandInvokeError):
            await interaction.followup.send("countdown_error: " + u_msg.NUM_OUTSIDE_ONE_AND_MAX_INTERVAL_ERR, ephemeral=True)
        else:
            print(error)


async def setup(client):
    await client.add_cog(Control(client))
