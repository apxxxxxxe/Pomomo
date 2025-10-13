import discord
from discord.ext import commands
from discord import app_commands, HTTPException

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
            
        # 移動前のチャンネルが存在する場合
        if before.channel:
            print(f'{member.display_name} left the channel {before.channel.name}.')
            session = vc_manager.get_connected_session(before.channel)
            if session:
                auto_shush = session.auto_shush
                if member in auto_shush.subs or auto_shush.all:
                    if session.state in [bot_enum.State.POMODORO, bot_enum.State.COUNTDOWN] and \
                            (getattr(session.ctx, 'voice_client', None) or session.ctx.guild.voice_client):
                        print(f"unmuting {member.display_name}")
                        try:
                            await member.edit(mute=False)
                        except HTTPException as e:
                            if e.text == "Target user is not connected to voice.":
                                await session.start_channel.send(f"ちょっと待って、{member.mention}！　サーバミュートが解除できていません。\n一度ボイスチャンネルに再接続して `/autoshush` コマンドを実行してください。")
                            else:
                                print(e.text)

        # 移動後のチャンネルが存在する場合
        if after.channel:
            print(f'{member.display_name} joined the channel {after.channel.name}.')
            session = vc_manager.get_connected_session(after.channel)
            if session:
                auto_shush = session.auto_shush
                if member in auto_shush.subs or auto_shush.all:
                    if session.state in [bot_enum.State.POMODORO, bot_enum.State.COUNTDOWN] and \
                            (getattr(session.ctx, 'voice_client', None) or session.ctx.guild.voice_client) and not (member.voice.mute):
                        print(f"muting {member.display_name}")
                        await auto_shush.safe_edit_member(member, unmute=False)
        
async def setup(client):
    await client.add_cog(Subscribe(client))
