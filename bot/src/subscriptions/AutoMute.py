import logging

from discord.ext.commands import Context
from discord.channel import TextChannel, VoiceChannel
from discord import User, Member, HTTPException

from ..voice_client import vc_accessor
from .Subscription import Subscription
from configs.logging_config import get_logger

logger = get_logger(__name__)


ALL = "all"


class AutoMutePermissionError(Exception):
    """AutoMute機能での権限エラー"""
    pass


class AutoMute(Subscription):

    def __init__(self):
        super().__init__()
        self.all = False

    def _get_author(self, ctx) -> Member | None:
        """Get author from either Context or Interaction"""
        guild = self._get_guild(ctx)
        if guild is None:
            return None
        m : Member | User = ctx.author if hasattr(ctx, 'author') else ctx.user
        return guild.get_member(m.id) if m else None
    
    def _get_guild(self, ctx):
        """Get guild from either Context or Interaction"""
        return ctx.guild
    
    def _get_channel(self, ctx) -> TextChannel | VoiceChannel | None:
        """Get channel from either Context or Interaction"""
        return ctx.channel
    
    async def _send_message(self, ctx, message):
        """Send message via either Context or Interaction"""
        if hasattr(ctx, 'response') and not ctx.response.is_done():
            await ctx.response.send_message(message)
        elif hasattr(ctx, 'followup'):
            await ctx.followup.send(message)
        else:
            await ctx.send(message)

    async def safe_edit_member(self, member: Member, unmute=False, channel_name=None):
        """安全にメンバーの音声状態を編集する"""
        try:
            await member.edit(mute=not unmute)
            action = "unmuted" if unmute else "muted"
            logger.info(f"Successfully {action} {member.display_name}")
        except HTTPException as e:
            if e.code == 40032:  # Target user is not connected to voice
                logger.info(f"Cannot edit {member.display_name}: User disconnected from voice")
            elif e.code == 50013:  # Missing Permissions
                action = "unmute" if unmute else "mute"
                channel_info = f" in {channel_name}" if channel_name else ""
                logger.info(f"Cannot {action} {member.display_name}: Missing permissions{channel_info}")
            else:
                logger.warning(f"Failed to edit member {member.display_name}: {e}")
        except Exception as e:
            logger.warning(f"Failed to edit member {member.display_name}: {e}")

    async def mute(self, ctx: Context, who=None):
        vc_members = vc_accessor.get_true_members_in_voice_channel(ctx)
        vc = vc_accessor.get_voice_channel(ctx)
        if not vc:
            await self._send_message(ctx, 'ボイスチャンネルに接続されていません。')
            return
        # ステージチャンネルは非対応
        is_stage = hasattr(vc, 'type') and vc.type.name == 'stage_voice'
        if is_stage:
            await self._send_message(ctx, 'ステージチャンネルではAuto-muteはサポートされていません。')
            return
        
        if who == ALL or self.all:
            for member in vc_members:
                await self.safe_edit_member(member)

    async def unmute(self, ctx: Context, who=None):
        vc_members = vc_accessor.get_true_members_in_voice_channel(ctx)
        vc = vc_accessor.get_voice_channel(ctx)
        if not vc:
            await self._send_message(ctx, 'ボイスチャンネルに接続されていません。')
            return
        # ステージチャンネルは非対応
        is_stage = hasattr(vc, 'type') and vc.type.name == 'stage_voice'
        if is_stage:
            await self._send_message(ctx, 'ステージチャンネルではAuto-muteはサポートされていません。')
            return
        
        if who == ALL or self.all:
            for member in vc_members:
                await self.safe_edit_member(member, unmute=True)

    async def handle_all(self, ctx, enable=None):
        logger.debug("Getting voice channel for automute")
        from ..voice_client import vc_accessor
        
        # ボイスチャンネルを取得（ミュート操作が実際に行われる場所）
        voice_channel = vc_accessor.get_voice_channel(ctx)
        if not voice_channel:
            await self._send_message(ctx, 'ボイスチャンネルに接続されていません。')
            return
        
        # ボイスチャンネルでのボットの権限チェック
        bot_member = voice_channel.guild.me
        bot_permissions = voice_channel.permissions_for(bot_member)
        if not (bot_permissions.mute_members or bot_permissions.administrator):
            # 権限不足の場合は例外を投げる
            permission_error_msg = f'ボットが `{voice_channel.name}` ボイスチャンネルでメンバーをミュートする権限を持っていません。\nbotアカウント `{bot_member.name}` へ `{voice_channel.name}` ボイスチャンネルでの「メンバーをミュートする」権限を付与してください。'
            raise AutoMutePermissionError(permission_error_msg)
            
        # enableが明示的に指定されている場合はその値を使用、そうでなければトグル
        if enable is not None:
            target_state = enable
        else:
            target_state = not self.all
            
        if target_state and not self.all:
            self.all = True
            await self.mute(ctx, ALL)
        elif not target_state and self.all:
            self.all = False
            await self.unmute(ctx, ALL)
