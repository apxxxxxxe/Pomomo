from discord.ext.commands import Context
from discord.channel import TextChannel, VoiceChannel
from discord import User, Member
from typing import Union

from ..voice_client import vc_accessor
from configs import bot_enum
from .Subscription import Subscription


ALL = "all"


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

    async def safe_edit_member(self, member: Member, unmute=False):
        """安全にメンバーの音声状態を編集する"""
        try:
            await member.edit(mute=not unmute)
        except Exception as e:
            print(f"DEBUG: Failed to edit member {member.display_name}: {e}")

    async def mute(self, ctx: Context, who=None):
        vc_members = vc_accessor.get_true_members_in_voice_channel(ctx)
        vc = vc_accessor.get_voice_channel(ctx)
        
        # ステージチャンネルは非対応
        is_stage = hasattr(vc, 'type') and vc.type.name == 'stage_voice'
        if is_stage:
            await self._send_message(ctx, 'ステージチャンネルではAuto-muteはサポートされていません。')
            return
        
        if who == ALL:
            for member in vc_members:
                await self.safe_edit_member(member)
        elif who:
            await self.safe_edit_member(who)
        elif self.all:
            for member in vc_members:
                await self.safe_edit_member(member)
        else:
            for member in vc_members:
                if member in self.subs:
                    await self.safe_edit_member(member)

    async def unmute(self, ctx: Context, who=None):
        vc_members = vc_accessor.get_true_members_in_voice_channel(ctx)
        vc = vc_accessor.get_voice_channel(ctx)
        
        # ステージチャンネルは非対応
        is_stage = hasattr(vc, 'type') and vc.type.name == 'stage_voice'
        if is_stage:
            await self._send_message(ctx, 'ステージチャンネルではAuto-muteはサポートされていません。')
            return
        
        if who == ALL or self.all:
            for member in vc_members:
                await self.safe_edit_member(member, unmute=True)
        elif who:
            await self.safe_edit_member(who, unmute=True)
        else:
            for member in vc_members:
                if member in self.subs:
                    await self.safe_edit_member(member, unmute=True)

    async def handle_all(self, ctx):
        print("getting author...")
        author = self._get_author(ctx)
        print("checking permissions...")
        if not author:
            await self._send_message(ctx, 'ユーザー情報が取得できません。')
            return
        channel = self._get_channel(ctx)
        if not channel:
            await self._send_message(ctx, 'チャンネル情報が取得できません。')
            return
        permissions = channel.permissions_for(author)
        if not permissions:
            await self._send_message(ctx, '権限情報が取得できません。')
            return
        if not (permissions.mute_members or permissions.administrator):
            await self._send_message(ctx, '他のメンバーをミュートする権限がありません。')
            return
        if self.all:
            self.all = False
            await self.unmute(ctx, ALL)
        else:
            self.all = True
            await self.mute(ctx, ALL)

    async def remove_sub(self, ctx):
        vc_members = vc_accessor.get_true_members_in_voice_channel(ctx)
        vc_name = vc_accessor.get_voice_channel(ctx).name
        if self.all:
            await self._send_message(ctx, f'{vc_name}チャンネルの全メンバーのAuto-muteは既にオンです。')
            return
        author = self._get_author(ctx)
        print(f'Removed {author} from auto-mute subscribers.')
        self.subs.remove(author)
        await self._send_message(ctx, f'{author.display_name}のAuto-mute購読を削除しました！')
        if author in vc_members:
            await self.unmute(ctx, author)

    async def add_sub(self, session, author: User):
        ctx = session.ctx
        vc_members = vc_accessor.get_true_members_in_voice_channel(ctx)
        vc_name = vc_accessor.get_voice_channel(ctx).name
        if self.all:
            await self._send_message(ctx, f'{vc_name}チャンネルの全メンバーのAuto-muteは既にオンです。')
            return
        self.subs.add(author)
        if session.state in [bot_enum.State.POMODORO, bot_enum.State.COUNTDOWN] and author in vc_members:
            await self.mute(ctx, author)
