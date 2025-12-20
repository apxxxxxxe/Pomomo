import logging

import discord
from discord.ext import commands
from discord import app_commands, HTTPException

from src.session import session_manager
from src.voice_client import vc_accessor as vc_accessor, vc_manager as vc_manager
from src.utils import voice_validation
from src.subscriptions.AutoMute import AutoMutePermissionError
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
            await self._safe_interaction_response(interaction, u_msg.NO_ACTIVE_SESSION_ERR)
            return
            
        if not vc_accessor.get_voice_channel_interaction(interaction):
            await self._safe_interaction_response(interaction, u_msg.AUTOMUTE_REQUIRES_BOT_IN_VC)
            return
            
        channel_name = vc_accessor.get_voice_channel(session.ctx).name
        if not await voice_validation.require_same_voice_channel(interaction):
            bot_name = interaction.client.user.display_name
            await self._safe_interaction_response(interaction, u_msg.SAME_VOICE_CHANNEL_REQUIRED_ERR.format(command='/enableautomute', bot_name=bot_name, channel_name=channel_name))
            return
            
        auto_mute = session.auto_mute
        if auto_mute.all:
            await self._safe_interaction_response(interaction, u_msg.AUTOMUTE_ALREADY_ENABLED.format(channel_name=channel_name))
            return
        
        # 時間のかかる処理開始前にdefer
        if not await self._safe_interaction_response(interaction, "", use_defer=True):
            # defer失敗時は直接チャンネルに送信
            await interaction.channel.send(f"{interaction.user.mention} automuteの有効化を開始します...", silent=True)
        
        try:
            # 休憩中かどうかを確認
            if session.state in bot_enum.State.BREAK_STATES:
                # 休憩中の場合：AutoMute機能を有効にするが即座のミュートは行わない
                auto_mute.all = True
                success_message = f'> -# {interaction.user.display_name} さんが`/enableautomute`を使用しました\n{channel_name}ボイスチャンネルのautomuteをオンにしました！\n現在は休憩中のため、次の作業時間開始時から強制ミュートが適用されます🤫'
                try:
                    await interaction.delete_original_response()
                    await interaction.channel.send(success_message, silent=True)
                except discord.errors.HTTPException as e:
                    if e.code == 10062:  # Unknown interaction - already handled
                        await interaction.channel.send(success_message, silent=True)
                    else:
                        logger.warning(f"Failed to delete original response: {e}")
                        await interaction.channel.send(success_message, silent=True)
                logger.info(f"Enabled automute for all users in {channel_name} by {interaction.user} (break state: {session.state})")
            else:
                # 作業中の場合：AutoMute機能を有効にして即座にミュート
                try:
                    await auto_mute.handle_all(interaction, enable=True)
                    success_message = f'> -# {interaction.user.display_name} さんが`/enableautomute`を使用しました\n{channel_name}ボイスチャンネルのautomuteをオンにしました！\n参加者は作業時間の間は強制ミュートされます🤫'
                    try:
                        await interaction.delete_original_response()
                        await interaction.channel.send(success_message, silent=True)
                    except discord.errors.HTTPException as e:
                        if e.code == 10062:  # Unknown interaction - already handled
                            await interaction.channel.send(success_message, silent=True)
                        else:
                            logger.warning(f"Failed to delete original response: {e}")
                            await interaction.channel.send(success_message, silent=True)
                    logger.info(f"Enabled automute for all users in {channel_name} by {interaction.user} (work state: {session.state})")
                except AutoMutePermissionError as permission_error:
                    # 権限エラー時は持続的なephemeralメッセージを送信
                    logger.warning(f"Permission error in enableautomute: {permission_error}")
                    try:
                        await interaction.delete_original_response()
                    except:
                        pass  # delete失敗は無視
                    # 権限エラーメッセージを直接ephemeralで送信（消えない）
                    await self._safe_interaction_response(interaction, str(permission_error), ephemeral=True)
                    return  # 成功メッセージは送信しない
        except Exception as e:
            logger.error(f"Error in enableautomute: {e}")
            logger.exception("Exception details:")
            try:
                await interaction.delete_original_response()
            except:
                pass  # delete失敗は無視
            await interaction.channel.send(u_msg.AUTOMUTE_ENABLE_FAILED, silent=True)

    async def _safe_interaction_response(self, interaction: discord.Interaction, message: str, ephemeral: bool = True, use_defer: bool = False):
        """安全にインタラクションに応答する"""
        try:
            if use_defer:
                if not interaction.response.is_done():
                    await interaction.response.defer(ephemeral=ephemeral)
            else:
                if not interaction.response.is_done():
                    await interaction.response.send_message(message, ephemeral=ephemeral)
                else:
                    await interaction.followup.send(message, ephemeral=ephemeral)
            return True
        except discord.errors.HTTPException as e:
            if e.code == 10062:  # Unknown interaction
                logger.warning(f"Interaction expired for user {interaction.user.display_name}: {e}")
                try:
                    # インタラクション期限切れの場合、チャンネルに直接送信
                    await interaction.channel.send(f"{interaction.user.mention} {message}", silent=True)
                except Exception as fallback_error:
                    logger.error(f"Failed to send fallback message: {fallback_error}")
            elif e.code == 0:  # Service unavailable
                logger.warning(f"Discord API service unavailable for user {interaction.user.display_name}: {e}")
                try:
                    # API障害の場合も、チャンネルに直接送信を試行
                    await interaction.channel.send(f"{interaction.user.mention} {message}", silent=True)
                except Exception as fallback_error:
                    logger.error(f"Failed to send fallback message during API outage: {fallback_error}")
            else:
                logger.error(f"Unexpected HTTP error in interaction response: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error in interaction response: {e}")
            return False

    @app_commands.command(name="disableautomute", description="チャンネル内の全メンバーの自動ミュート機能を無効にする")
    async def disableautomute(self, interaction: discord.Interaction):
        session = await session_manager.get_session_interaction(interaction)
        if not session:
            await self._safe_interaction_response(interaction, u_msg.NO_ACTIVE_SESSION_ERR)
            return
            
        if not vc_accessor.get_voice_channel_interaction(interaction):
            await self._safe_interaction_response(interaction, u_msg.AUTOMUTE_REQUIRES_BOT_IN_VC)
            return
            
        channel_name = vc_accessor.get_voice_channel(session.ctx).name
        if not await voice_validation.require_same_voice_channel(interaction):
            bot_name = interaction.client.user.display_name
            await self._safe_interaction_response(interaction, u_msg.SAME_VOICE_CHANNEL_REQUIRED_ERR.format(command='/disableautomute', bot_name=bot_name, channel_name=channel_name))
            return
            
        auto_mute = session.auto_mute
        if not auto_mute.all:
            await self._safe_interaction_response(interaction, u_msg.AUTOMUTE_ALREADY_DISABLED.format(channel_name=channel_name))
            return
        
        # 時間のかかる処理開始前にdefer
        if not await self._safe_interaction_response(interaction, "", use_defer=True):
            # defer失敗時は直接チャンネルに送信
            await interaction.channel.send(f"{interaction.user.mention} automuteの無効化を開始します...", silent=True)
        
        try:
            await auto_mute.handle_all(interaction, enable=False)
            # 成功時のメッセージ送信
            success_message = f'> -# {interaction.user.display_name} さんが`/disableautomute`を使用しました\n{channel_name}ボイスチャンネルのautomuteをオフにしました'
            try:
                # defer()によるthinkingメッセージを削除して、チャンネルに送信
                await interaction.delete_original_response()
                await interaction.channel.send(success_message, silent=True)
            except discord.errors.HTTPException as e:
                if e.code == 10062:  # Unknown interaction - already handled
                    await interaction.channel.send(success_message, silent=True)
                else:
                    logger.warning(f"Failed to delete original response: {e}")
                    await interaction.channel.send(success_message, silent=True)
        except AutoMutePermissionError as permission_error:
            # 権限エラー時は持続的なephemeralメッセージを送信
            logger.warning(f"Permission error in disableautomute: {permission_error}")
            try:
                await interaction.delete_original_response()
            except:
                pass  # delete失敗は無視
            # 権限エラーメッセージを直接ephemeralで送信（消えない）
            await self._safe_interaction_response(interaction, str(permission_error), ephemeral=True)
            return  # 成功メッセージは送信しない
        except Exception as e:
            logger.error(f"Error in disableautomute: {e}")
            logger.exception("Exception details:")
            try:
                await interaction.delete_original_response()
            except:
                pass  # delete失敗は無視
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
                logger.info(f'No channel change for {member.display_name}, but logged mute/deafen state changes if any.')
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
            logger.debug(f"DEBUG: Checking session for guild {before.channel.guild.id} (before.channel.id: {before.channel.id})")
            
            session = vc_manager.get_connected_session(str(before.channel.guild.id))
            logger.debug(f"DEBUG: Session found: {session is not None}")
            
            if session and session.ctx:
                session_vc = vc_accessor.get_voice_channel(session.ctx)
                logger.debug(f"DEBUG: Session voice channel: {session_vc.name if session_vc else None} (ID: {session_vc.id if session_vc else None})")
                logger.debug(f"DEBUG: Before channel: {before.channel.name} (ID: {before.channel.id})")
                logger.debug(f"DEBUG: Channel ID match: {str(session_vc.id) == str(before.channel.id) if session_vc else False}")
                
                if session_vc and str(session_vc.id) == str(before.channel.id):
                    auto_mute = session.auto_mute
                    logger.debug(f"DEBUG: AutoMute object: {auto_mute}")
                    logger.debug(f"DEBUG: AutoMute.all attribute: {getattr(auto_mute, 'all', 'MISSING')}")
                    logger.debug(f"DEBUG: AutoMute enabled: {auto_mute.all if hasattr(auto_mute, 'all') else 'NO_ALL_ATTR'}")
                    
                    if auto_mute and hasattr(auto_mute, 'all') and auto_mute.all:
                        logger.debug(f"DEBUG: Session state: {session.state}")
                        logger.debug(f"DEBUG: Work states: {bot_enum.State.WORK_STATES}")
                        logger.debug(f"DEBUG: State in work states: {session.state in bot_enum.State.WORK_STATES}")
                        
                        voice_client_ctx = getattr(session.ctx, 'voice_client', None)
                        voice_client_guild = session.ctx.guild.voice_client
                        logger.debug(f"DEBUG: Voice client (ctx): {voice_client_ctx is not None}")
                        logger.debug(f"DEBUG: Voice client (guild): {voice_client_guild is not None}")
                        
                        if session.state in bot_enum.State.WORK_STATES and \
                                (voice_client_ctx or voice_client_guild):
                            logger.info(f"Unmuting {member.display_name} due to leaving automute channel")
                            
                            # 移動先チャンネルでの権限確認（移動先がある場合のみ）
                            can_unmute_in_destination = True
                            if after.channel:
                                bot_member = after.channel.guild.me
                                bot_permissions = after.channel.permissions_for(bot_member)
                                can_unmute_in_destination = bot_permissions.mute_members or bot_permissions.administrator
                                logger.debug(f"DEBUG: Can unmute in destination {after.channel.name}: {can_unmute_in_destination}")
                            
                            try:
                                await member.edit(mute=False)
                                logger.info(f"Successfully unmuted {member.display_name}")
                            except HTTPException as e:
                                if e.code == 40032:  # Target user is not connected to voice
                                    logger.info(f"Cannot unmute {member.display_name}: User disconnected from voice")
                                    await session.ctx.channel.send(f"ちょっと待って、{member.mention}！　あなたのサーバミュートが解除できていません。\n一度ボイスチャンネルに再接続してから次のどちらかの手順を選んでください。\n1. **#{before.channel.name}** に戻って `/disableautomute` コマンドを実行する\n2. 別のボイスチャンネルに移動してから通話を離脱する", silent=True)
                                elif e.code == 50013:  # Missing Permissions
                                    logger.info(f"Cannot unmute {member.display_name}: Missing permissions in destination channel")
                                    destination_channel = after.channel.name if after.channel else "不明なチャンネル"
                                    
                                    # ボットがミュート権限を持ち、セッション中でないボイスチャンネルを検索
                                    guild = after.channel.guild if after.channel else before.channel.guild
                                    available_voice_channel = self._find_available_voice_channel(guild, exclude_session_channels=True)
                                    
                                    if available_voice_channel:
                                        message = f"ちょっと待って、{member.mention}！　{destination_channel}でのミュート解除権限がないため、あなたのサーバミュートが解除できていません。\n次のどちらかの手順を選んでください。\n1. **#{before.channel.name}** に戻って `/disableautomute` コマンドを実行する\n2. **#{available_voice_channel.name}** に移動してから通話を離脱する"
                                    else:
                                        message = f"ちょっと待って、{member.mention}！　{destination_channel}でのミュート解除権限がないため、あなたのサーバミュートが解除できていません。\n**#{before.channel.name}** に戻って `/disableautomute` コマンドを実行してください。"
                                    
                                    await session.ctx.channel.send(message, silent=True)
                                else:
                                    logger.warning(f"Failed to unmute {member.display_name}: {e}")
                                    await session.ctx.channel.send(f"ちょっと待って、{member.mention}！　あなたのサーバミュートの解除でエラーが発生しました。\n`/disableautomute` コマンドを実行してください。", silent=True)
                        else:
                            logger.debug(f"DEBUG: Skipping unmute for {member.display_name} - conditions not met")
                    else:
                        logger.debug(f"DEBUG: AutoMute not enabled for {member.display_name} (auto_mute={auto_mute}, all={getattr(auto_mute, 'all', 'MISSING')}), skipping unmute")
                else:
                    logger.debug(f"DEBUG: Channel mismatch or session_vc is None for {member.display_name}, skipping unmute")
            else:
                logger.debug(f"DEBUG: No session or session.ctx found for {member.display_name}, skipping unmute")

        # 移動後のチャンネルが存在する場合
        if after.channel:
            logger.info(f'{member.display_name} joined the channel {after.channel.name}.')
            
            # サーバーミュート状態のユーザーを自動的にミュート解除
            if after.mute:
                logger.info(f'{member.display_name} is server muted, attempting auto-unmute')
                await self._handle_server_muted_user_join(member, before, after)
            
            session = vc_manager.get_connected_session(str(after.channel.guild.id))
            if session and session.ctx:
                session_vc = vc_accessor.get_voice_channel(session.ctx)
                if session_vc and str(session_vc.id) == str(after.channel.id):
                    auto_mute = session.auto_mute
                    if auto_mute.all:
                        if session.state in bot_enum.State.WORK_STATES and \
                                (getattr(session.ctx, 'voice_client', None) or session.ctx.guild.voice_client) and member.voice and not member.voice.mute:
                            logger.info(f"Muting {member.display_name} due to joining automute channel")
                            await auto_mute.safe_edit_member(member, unmute=False, channel_name=after.channel.name)

    def _find_available_voice_channel(self, guild, exclude_session_channels=False):
        """ボットがミュート権限を持つボイスチャンネルを検索
        
        Args:
            guild: 対象のギルド
            exclude_session_channels: セッション中チャンネルを除外するか
        """
        session_vc_id = None
        if exclude_session_channels:
            # アクティブなセッションのボイスチャンネルIDを取得
            session = vc_manager.get_connected_session(str(guild.id))
            if session and session.ctx:
                session_vc = vc_accessor.get_voice_channel(session.ctx)
                if session_vc:
                    session_vc_id = str(session_vc.id)
        
        for vc in guild.voice_channels:
            bot_permissions = vc.permissions_for(guild.me)
            if bot_permissions.mute_members or bot_permissions.administrator:
                # セッション除外が有効で、このチャンネルがセッション中の場合はスキップ
                if exclude_session_channels and session_vc_id and str(vc.id) == session_vc_id:
                    continue
                return vc
        return None

    async def _handle_server_muted_user_join(self, member, before, after):
        """サーバーミュート状態のユーザーがボイスチャンネルに参加した際の処理"""
        try:
            # セッション中チャンネルからの移動かをチェック（その場合は既存システムが処理するのでスキップ）
            if before.channel:
                session = vc_manager.get_connected_session(str(before.channel.guild.id))
                if session and session.ctx:
                    session_vc = vc_accessor.get_voice_channel(session.ctx)
                    if session_vc and str(session_vc.id) == str(before.channel.id):
                        auto_mute = session.auto_mute
                        if auto_mute and hasattr(auto_mute, 'all') and auto_mute.all:
                            logger.info(f"Skipping auto-unmute for {member.display_name} - moved from active automute session channel")
                            return

            # セッション中チャンネルかどうかをチェック（強制ミュート対象チャンネルは除外）
            session = vc_manager.get_connected_session(str(after.channel.guild.id))
            if session and session.ctx:
                session_vc = vc_accessor.get_voice_channel(session.ctx)
                if session_vc and str(session_vc.id) == str(after.channel.id):
                    auto_mute = session.auto_mute
                    if auto_mute and hasattr(auto_mute, 'all') and auto_mute.all and session.state in bot_enum.State.WORK_STATES:
                        logger.info(f"Skipping auto-unmute for {member.display_name} - joined active automute session channel")
                        return

            # ボットがミュート権限を持つかチェック
            bot_member = after.channel.guild.me
            bot_permissions = after.channel.permissions_for(bot_member)
            can_unmute = bot_permissions.mute_members or bot_permissions.administrator

            if can_unmute:
                # ミュート解除を試行
                await member.edit(mute=False)
                logger.info(f"Successfully auto-unmuted {member.display_name} in {after.channel.name}")
            else:
                # 権限がない場合、適切なテキストチャンネルで通知
                logger.info(f"Cannot auto-unmute {member.display_name} in {after.channel.name}: Missing permissions")
                await self._send_unmute_instruction(member, after.channel)

        except HTTPException as e:
            if e.code == 40032:  # Target user is not connected to voice
                logger.info(f"Cannot auto-unmute {member.display_name}: User disconnected from voice")
            elif e.code == 50013:  # Missing Permissions
                logger.info(f"Cannot auto-unmute {member.display_name}: Missing permissions")
                await self._send_unmute_instruction(member, after.channel)
            else:
                logger.warning(f"Failed to auto-unmute {member.display_name}: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error in auto-unmute for {member.display_name}: {e}")

    def _find_target_text_channel(self, guild, voice_channel):
        """メッセージ送信先のテキストチャンネルを優先順位に基づいて選択
        
        Args:
            guild: Discord guild object
            voice_channel: ユーザーが入っているボイスチャンネル
        
        Returns:
            discord.TextChannel: メッセージ送信先のテキストチャンネル、見つからない場合はNone
        """
        # 1. ボイスチャンネルと同名のテキストチャンネルを検索
        for channel in guild.text_channels:
            if channel.name == voice_channel.name:
                # ボットが送信権限を持つかチェック
                bot_permissions = channel.permissions_for(guild.me)
                if bot_permissions.send_messages:
                    return channel
        
        # 2. "General" テキストチャンネルを検索
        for channel in guild.text_channels:
            if channel.name == "General":
                # ボットが送信権限を持つかチェック
                bot_permissions = channel.permissions_for(guild.me)
                if bot_permissions.send_messages:
                    return channel
        
        # 3. 最初の利用可能なテキストチャンネルを使用
        for channel in guild.text_channels:
            bot_permissions = channel.permissions_for(guild.me)
            if bot_permissions.send_messages:
                return channel
        
        return None

    async def _send_unmute_instruction(self, member, voice_channel):
        """ミュート解除できない場合の通知を送信"""
        try:
            guild = voice_channel.guild
            
            # ボットがミュート権限を持つボイスチャンネルを検索
            available_voice_channel = self._find_available_voice_channel(guild)
            
            # 新しいチャンネル選択ロジックを使用
            target_channel = self._find_target_text_channel(guild, voice_channel)
            
            if target_channel:
                # メッセージ内容を決定
                if available_voice_channel:
                    message = f"{member.mention} あなたのサーバーミュートを解除しようとしましたが、ボイスチャンネル **#{voice_channel.name}** ではPomomoに権限がありませんでした。\n別のボイスチャンネル、例えば **#{available_voice_channel.name}** に一旦移動してから戻ってきてください。"
                    logger.info(f"Sent unmute instruction to {member.display_name} in #{target_channel.name} (suggested voice channel: #{available_voice_channel.name})")
                else:
                    message = f"{member.mention} あなたのサーバーミュートを解除しようとしましたが、ボイスチャンネル **#{voice_channel.name}** ではPomomoに権限がありませんでした。\n別のボイスチャンネルに一旦移動してから戻ってきてください。"
                    logger.info(f"Sent unmute instruction to {member.display_name} in #{target_channel.name} (no suitable voice channel found)")
                
                await target_channel.send(message, silent=True)
            else:
                logger.warning(f"Could not find suitable text channel to send unmute instruction for {member.display_name}")
                
        except Exception as e:
            logger.warning(f"Failed to send unmute instruction for {member.display_name}: {e}")
        
async def setup(client):
    await client.add_cog(Subscribe(client))
