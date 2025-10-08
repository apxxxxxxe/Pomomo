import discord
from discord.ext import commands
from discord import app_commands

from src.session import session_manager
from src.subscriptions import AutoShush
from src.voice_client import vc_accessor as vc_accessor, vc_manager as vc_manager
from configs import bot_enum


class Subscribe(commands.Cog):

    def __init__(self, client):
        self.client = client

    @app_commands.command(name="autoshush", description="Toggle auto-shush functionality")
    @app_commands.describe(who="自動ミュート対象: 'all'で全員、空欄で自分のみ")
    async def autoshush(self, interaction: discord.Interaction, who: str = ''):
        session = await session_manager.get_session_interaction(interaction)
        if session:
            if not vc_accessor.get_voice_channel_interaction(interaction):
                await interaction.response.send_message('auto-shushを使用するにはPomomoが音声チャンネルにいる必要があります。')
                return
            auto_shush = session.auto_shush
            if who.lower() == AutoShush.ALL:
                await auto_shush.handle_all(interaction)
                if auto_shush.all:
                   await interaction.response.send_message('通話参加者全員のautoshushをオンにしました')
                else:
                   await interaction.response.send_message('通話参加者全員のautoshushをオフにしました')
            elif interaction.user in auto_shush.subs:
                await auto_shush.remove_sub(interaction)
                await interaction.response.send_message(who or interaction.user.name + ' のautoshushをオフにしました')
            else:
                await auto_shush.add_sub(session, interaction.user)
                await interaction.response.send_message(who or interaction.user.name + ' のautoshushをオンにしました')
        else:
            await interaction.response.send_message('アクティブなセッションがありません。', ephemeral=True)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # ボットは処理しない
        if member.bot:
            return

        # ボイスチャンネルの変更がない場合は処理しない
        if before.channel == after.channel:
            print(f'No channel change for {member.display_name}, ignoring.')
            return

        print(f'Voice state update for {member.display_name}: {before.channel} -> {after.channel}')
            
        # ユーザーが通話から完全に離脱した場合（before.channel あり、after.channel なし）
        if before.channel and not after.channel:
            print(f'{member.display_name} left the channel {before.channel.name}.')
            session = vc_manager.get_connected_session(before.channel)
            if session:
                auto_shush = session.auto_shush
                # autostushをsubscribeしている、またはAllに設定されている場合
                if member in auto_shush.subs or member in auto_shush.all:
                    if member.voice.mute:
                        # ミュートされている場合は解除
                        await auto_shush.safe_edit_member(member, unmute=True)
        
        # ユーザーがチャンネル間を移動した場合
        elif before.channel and after.channel:
            before_session = vc_manager.get_connected_session(before.channel)
            after_session = vc_manager.get_connected_session(after.channel)
            if before_session:
                print(f"Handling auto-shush for {member.display_name} leaving {before.channel.name}")
                auto_shush = before_session.auto_shush
                # autostushをsubscribeしている、またはAllに設定されている場合
                if member in auto_shush.subs or member in auto_shush.all:
                    if member.voice.mute:
                        # ミュートされている場合は解除
                        await auto_shush.safe_edit_member(member, unmute=True)

            if after_session:
                print(f"Handling auto-shush for {member.display_name} joining {after.channel.name}")
                auto_shush = after_session.auto_shush
                if member in auto_shush.subs or auto_shush.all:
                    if after_session.state in [bot_enum.State.POMODORO, bot_enum.State.COUNTDOWN] and \
                            (getattr(after_session.ctx, 'voice_client', None) or after_session.ctx.guild.voice_client) and not (member.voice.mute):
                        await auto_shush.shush(after_session.ctx, member)


async def setup(client):
    await client.add_cog(Subscribe(client))
