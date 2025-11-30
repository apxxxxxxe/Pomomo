import logging

import discord
from discord.ext import commands
from discord import app_commands, HTTPException

from src.session import session_manager
from src.voice_client import vc_accessor as vc_accessor, vc_manager as vc_manager
from src.utils import voice_validation
from configs import bot_enum, user_messages as u_msg
from configs.logging_config import get_logger

logger = get_logger(__name__)


class Subscribe(commands.Cog):

    def __init__(self, client):
        self.client = client

    @app_commands.command(name="enableautomute", description="チャンネル内の全メンバーの自動ミュート機能を有効にする")
    async def enableautomute(self, interaction: discord.Interaction):
        session = await session_manager.get_session_interaction(interaction)
        if not session:
            await interaction.response.send_message(u_msg.NO_ACTIVE_SESSION_ERR, ephemeral=True)
            return
            
        if not vc_accessor.get_voice_channel_interaction(interaction):
            await interaction.response.send_message(u_msg.AUTOMUTE_REQUIRES_BOT_IN_VC, ephemeral=True)
            return
            
        channel_name = vc_accessor.get_voice_channel(session.ctx).name
        if not await voice_validation.require_same_voice_channel(interaction):
            bot_name = interaction.client.user.display_name
            await interaction.response.send_message(u_msg.SAME_VOICE_CHANNEL_REQUIRED_ERR.format(command='/enableautomute', bot_name=bot_name, channel_name=channel_name), ephemeral=True)
            return
            
        auto_mute = session.auto_mute
        if auto_mute.all:
            await interaction.response.send_message(u_msg.AUTOMUTE_ALREADY_ENABLED.format(channel_name=channel_name), ephemeral=True)
            return
        
        # 時間のかかる処理開始前にdefer
        await interaction.response.defer(ephemeral=True)
        
        try:
            await auto_mute.handle_all(interaction)
            # defer()によるthinkingメッセージを削除して、チャンネルに送信
            await interaction.delete_original_response()
            await interaction.channel.send(f'> -# {interaction.user.display_name} さんが`/enableautomute`を使用しました\n{channel_name}ボイスチャンネルのautomuteをオンにしました！\n参加者は作業時間の間は強制ミュートされます🤫', silent=True)
            logger.info(f"Enabled automute for all users in {channel_name} by {interaction.user}")
        except Exception as e:
            logger.error(f"Error in enableautomute: {e}")
            logger.exception("Exception details:")
            await interaction.delete_original_response()
            await interaction.channel.send(u_msg.AUTOMUTE_ENABLE_FAILED, silent=True)

    @app_commands.command(name="disableautomute", description="チャンネル内の全メンバーの自動ミュート機能を無効にする")
    async def disableautomute(self, interaction: discord.Interaction):
        session = await session_manager.get_session_interaction(interaction)
        if not session:
            await interaction.response.send_message(u_msg.NO_ACTIVE_SESSION_ERR, ephemeral=True)
            return
            
        if not vc_accessor.get_voice_channel_interaction(interaction):
            await interaction.response.send_message(u_msg.AUTOMUTE_REQUIRES_BOT_IN_VC, ephemeral=True)
            return
            
        channel_name = vc_accessor.get_voice_channel(session.ctx).name
        if not await voice_validation.require_same_voice_channel(interaction):
            bot_name = interaction.client.user.display_name
            await interaction.response.send_message(u_msg.SAME_VOICE_CHANNEL_REQUIRED_ERR.format(command='/disableautomute', bot_name=bot_name, channel_name=channel_name), ephemeral=True)
            return
            
        auto_mute = session.auto_mute
        if not auto_mute.all:
            await interaction.response.send_message(u_msg.AUTOMUTE_ALREADY_DISABLED.format(channel_name=channel_name), ephemeral=True)
            return
        
        # 時間のかかる処理開始前にdefer
        await interaction.response.defer(ephemeral=True)
        
        try:
            await auto_mute.handle_all(interaction)
            # defer()によるthinkingメッセージを削除して、チャンネルに送信
            await interaction.delete_original_response()
            await interaction.channel.send(f'> -# {interaction.user.display_name} さんが`/disableautomute`を使用しました\n{channel_name}ボイスチャンネルのautomuteをオフにしました', silent=True)
        except Exception as e:
            logger.error(f"Error in disableautomute: {e}")
            logger.exception("Exception details:")
            await interaction.delete_original_response()
            await interaction.channel.send(u_msg.AUTOMUTE_DISABLE_FAILED, silent=True)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # ボットは処理しない
        if member.bot:
            return

        # ボイスチャンネルの変更がない場合でも、ミュート/デフン状態の変更をログに記録
        if before.channel == after.channel:
            # ミュート状態の変更を確認
            if before.self_mute != after.self_mute:
                state_change = "muted" if after.self_mute else "unmuted"
                logger.info(f'{member.display_name} {state_change} themselves in {after.channel.name if after.channel else "no channel"}')
            if before.mute != after.mute:
                state_change = "server muted" if after.mute else "server unmuted"
                logger.info(f'{member.display_name} was {state_change} in {after.channel.name if after.channel else "no channel"}')
            
            # デフン状態の変更を確認
            if before.self_deaf != after.self_deaf:
                state_change = "deafened" if after.self_deaf else "undeafened"
                logger.info(f'{member.display_name} {state_change} themselves in {after.channel.name if after.channel else "no channel"}')
            if before.deaf != after.deaf:
                state_change = "server deafened" if after.deaf else "server undeafened"
                logger.info(f'{member.display_name} was {state_change} in {after.channel.name if after.channel else "no channel"}')
                
            # チャンネル変更がない場合はここで処理終了
            if before.channel == after.channel:
                logger.debug(f'No channel change for {member.display_name}, but logged mute/deafen state changes if any.')
                return

        logger.info(f'Voice state update for {member.display_name}: {before.channel} -> {after.channel}')
        
        # チャンネル変更時のミュート/デフン状態もログに記録
        if before.channel != after.channel:
            # 移動前後のミュート状態の変更
            if before.self_mute != after.self_mute:
                state_change = "muted" if after.self_mute else "unmuted"
                logger.info(f'{member.display_name} {state_change} themselves during channel change')
            if before.mute != after.mute:
                state_change = "server muted" if after.mute else "server unmuted"
                logger.info(f'{member.display_name} was {state_change} during channel change')
                
            # 移動前後のデフン状態の変更
            if before.self_deaf != after.self_deaf:
                state_change = "deafened" if after.self_deaf else "undeafened"
                logger.info(f'{member.display_name} {state_change} themselves during channel change')
            if before.deaf != after.deaf:
                state_change = "server deafened" if after.deaf else "server undeafened"
                logger.info(f'{member.display_name} was {state_change} during channel change')
            
        # 移動前のチャンネルが存在する場合
        if before.channel:
            logger.info(f'{member.display_name} left the channel {before.channel.name}.')
            session = vc_manager.get_connected_session(str(before.channel.guild.id))
            if session and session.ctx:
                session_vc = vc_accessor.get_voice_channel(session.ctx)
                if session_vc and session_vc.id == before.channel.id:
                    auto_mute = session.auto_mute
                    if auto_mute.all:
                        if session.state in [bot_enum.State.POMODORO, bot_enum.State.COUNTDOWN] and \
                                (getattr(session.ctx, 'voice_client', None) or session.ctx.guild.voice_client):
                            logger.debug(f"Unmuting {member.display_name}")
                            try:
                                await member.edit(mute=False)
                            except HTTPException as e:
                                logger.warning(f"Failed to unmute {member.display_name}: {e}")
                                if e.text == "Target user is not connected to voice.":
                                    logger.warning(f"HTTPException text: {e.text}")
                                    await session.ctx.channel.send(f"ちょっと待って、{member.mention}！　あなたのサーバミュートが解除できていません。\n一度ボイスチャンネルに再接続してから次のどちらかの手順を選んでください。\n1. `/disableautomute` コマンドを実行する\n2. 別のボイスチャンネルに移動してから通話を離脱する", silent=True)
                                else:
                                    logger.warning(f"HTTPException text: {e.text}")

        # 移動後のチャンネルが存在する場合
        if after.channel:
            logger.info(f'{member.display_name} joined the channel {after.channel.name}.')
            session = vc_manager.get_connected_session(str(after.channel.guild.id))
            if session and session.ctx:
                session_vc = vc_accessor.get_voice_channel(session.ctx)
                if session_vc and session_vc.name == after.channel.name:
                    auto_mute = session.auto_mute
                    if auto_mute.all:
                        if session.state in [bot_enum.State.POMODORO, bot_enum.State.COUNTDOWN] and \
                                (getattr(session.ctx, 'voice_client', None) or session.ctx.guild.voice_client) and member.voice and not member.voice.mute:
                            logger.debug(f"Muting {member.display_name}")
                            await auto_mute.safe_edit_member(member, unmute=False)
        
async def setup(client):
    await client.add_cog(Subscribe(client))
