import discord
from discord.ext import commands
from discord import app_commands, HTTPException

from src.session import session_manager
from src.subscriptions import AutoMute
from src.voice_client import vc_accessor as vc_accessor, vc_manager as vc_manager
from configs import bot_enum


class Subscribe(commands.Cog):

    def __init__(self, client):
        self.client = client

    @app_commands.command(name="enableautomute", description="Enable auto-mute functionality")
    @app_commands.describe(who="自動ミュート対象: 'all'で全員、空欄で自分のみ")
    async def enableautomute(self, interaction: discord.Interaction, who: str = ''):
        session = await session_manager.get_session_interaction(interaction)
        if session:
            if not vc_accessor.get_voice_channel_interaction(interaction):
                await interaction.response.send_message('auto-muteを使用するにはPomomoが音声チャンネルにいる必要があります。')
                return
            auto_mute = session.auto_mute
            if who.lower() == AutoMute.ALL:
                if not auto_mute.all:
                    await auto_mute.handle_all(interaction)
                    await interaction.response.send_message('通話参加者全員のautomuteをオンにしました')
                    print("muted all users")
                else:
                    await interaction.response.send_message('通話参加者全員のautomuteは既にオンです')
            else:
                if interaction.user not in auto_mute.subs:
                    await auto_mute.add_sub(session, interaction.user)
                    await interaction.response.send_message((who or interaction.user.name) + ' のautomuteをオンにしました')
                else:
                    await interaction.response.send_message((who or interaction.user.name) + ' のautomuteは既にオンです')
        else:
            await interaction.response.send_message('アクティブなセッションがありません。', ephemeral=True)

    @app_commands.command(name="disableautomute", description="Disable auto-mute functionality")
    @app_commands.describe(who="自動ミュート解除対象: 'all'で全員、空欄で自分のみ")
    async def disableautomute(self, interaction: discord.Interaction, who: str = ''):
        session = await session_manager.get_session_interaction(interaction)
        if session:
            if not vc_accessor.get_voice_channel_interaction(interaction):
                await interaction.response.send_message('auto-muteを使用するにはPomomoが音声チャンネルにいる必要があります。')
                return
            auto_mute = session.auto_mute
            if who.lower() == AutoMute.ALL:
                if auto_mute.all:
                    await auto_mute.handle_all(interaction)
                    await interaction.response.send_message('通話参加者全員のautomuteをオフにしました')
                else:
                    await interaction.response.send_message('通話参加者全員のautomuteは既にオフです')
            else:
                if interaction.user in auto_mute.subs:
                    await auto_mute.remove_sub(interaction)
                    await interaction.response.send_message((who or interaction.user.name) + ' のautomuteをオフにしました')
                else:
                    await interaction.response.send_message((who or interaction.user.name) + ' のautomuteは既にオフです')
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
                auto_mute = session.auto_mute
                if member in auto_mute.subs or auto_mute.all:
                    if session.state in [bot_enum.State.POMODORO, bot_enum.State.COUNTDOWN] and \
                            (getattr(session.ctx, 'voice_client', None) or session.ctx.guild.voice_client):
                        print(f"unmuting {member.display_name}")
                        try:
                            await member.edit(mute=False)
                        except HTTPException as e:
                            if e.text == "Target user is not connected to voice.":
                                await session.start_channel.send(f"ちょっと待って、{member.mention}！　サーバミュートが解除できていません。\n一度ボイスチャンネルに再接続して `/enableautomute` または `/disableautomute` コマンドを実行してください。")
                            else:
                                print(e.text)

        # 移動後のチャンネルが存在する場合
        if after.channel:
            print(f'{member.display_name} joined the channel {after.channel.name}.')
            session = vc_manager.get_connected_session(after.channel)
            if session:
                auto_mute = session.auto_mute
                if member in auto_mute.subs or auto_mute.all:
                    if session.state in [bot_enum.State.POMODORO, bot_enum.State.COUNTDOWN] and \
                            (getattr(session.ctx, 'voice_client', None) or session.ctx.guild.voice_client) and not (member.voice.mute):
                        print(f"muting {member.display_name}")
                        await auto_mute.safe_edit_member(member, unmute=False)
        
async def setup(client):
    await client.add_cog(Subscribe(client))
