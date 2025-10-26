import discord
import discord
from discord.ext import commands
from discord import app_commands, HTTPException

from src.session import session_manager
from src.voice_client import vc_accessor as vc_accessor, vc_manager as vc_manager
from src.utils import voice_validation
from configs import bot_enum


class Subscribe(commands.Cog):

    def __init__(self, client):
        self.client = client

    @app_commands.command(name="enableautomute", description="チャンネル内の全メンバーの自動ミュート機能を有効にする")
    async def enableautomute(self, interaction: discord.Interaction):
        session = await session_manager.get_session_interaction(interaction)
        if not session:
            await interaction.response.send_message('アクティブなセッションがありません。', ephemeral=True)
            return
            
        if not vc_accessor.get_voice_channel_interaction(interaction):
            await interaction.response.send_message('automuteを使用するにはPomomoが音声チャンネルにいる必要があります。', ephemeral=True)
            return
            
        channel_name = vc_accessor.get_voice_channel(session.ctx).name
        if not await voice_validation.require_same_voice_channel(interaction):
            bot_name = interaction.client.user.display_name
            await interaction.response.send_message(f'`/enableautomute` コマンドは `{bot_name}` と同じボイスチャンネル `{channel_name}` に参加してから実行してください', ephemeral=True)
            return
            
        auto_mute = session.auto_mute
        if auto_mute.all:
            await interaction.response.send_message(f'{channel_name}ボイスチャンネルのautomuteは既にオンです', ephemeral=True)
            return
        
        # 時間のかかる処理開始前にdefer
        await interaction.response.defer(ephemeral=True)
        
        try:
            await auto_mute.handle_all(interaction)
            # silent=True指定のため、2度目のfollowupで本命のメッセージを送る
            await interaction.followup.send(f'処理が正常に完了しました',)
            await interaction.followup.send(f'> `{interaction.user.display_name}`さんが`/enableautomute`を使用しました\n{channel_name}ボイスチャンネルのautomuteをオンにしました！\n参加者は作業時間の間は強制ミュートされます🤫', silent=True, ephemeral=False)
            print("muted all users")
        except Exception as e:
            print(f"DEBUG: Error in enableautomute: {e}")
            await interaction.followup.send('automute機能の有効化に失敗しました。', ephemeral=True)

    @app_commands.command(name="disableautomute", description="チャンネル内の全メンバーの自動ミュート機能を無効にする")
    async def disableautomute(self, interaction: discord.Interaction):
        session = await session_manager.get_session_interaction(interaction)
        if not session:
            await interaction.response.send_message('アクティブなセッションがありません。', ephemeral=True)
            return
            
        if not vc_accessor.get_voice_channel_interaction(interaction):
            await interaction.response.send_message('automuteを使用するにはPomomoが音声チャンネルにいる必要があります。', ephemeral=True)
            return
            
        channel_name = vc_accessor.get_voice_channel(session.ctx).name
        if not await voice_validation.require_same_voice_channel(interaction):
            bot_name = interaction.client.user.display_name
            await interaction.response.send_message(f'`/enableautomute` コマンドは `{bot_name}` と同じボイスチャンネル `{channel_name}` に参加してから実行してください', ephemeral=True)
            return
            
        auto_mute = session.auto_mute
        if not auto_mute.all:
            await interaction.response.send_message(f'{channel_name}ボイスチャンネルのautomuteは既にオフです', ephemeral=True)
            return
        
        # 時間のかかる処理開始前にdefer
        await interaction.response.defer(ephemeral=True)
        
        try:
            await auto_mute.handle_all(interaction)
            # silent=True指定のため、2度目のfollowupで本命のメッセージを送る
            await interaction.followup.send(f'処理が正常に完了しました',)
            await interaction.followup.send(f'> `{interaction.user.display_name}`さんが`/enableautomute`を使用しました\n{channel_name}ボイスチャンネルのautomuteをオフにしました', silent=True, ephemeral=False)
        except Exception as e:
            print(f"DEBUG: Error in disableautomute: {e}")
            await interaction.followup.send('automute機能の無効化に失敗しました。', ephemeral=True)

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
            session = vc_manager.get_connected_session(str(before.channel.guild.id))
            session_vc = vc_accessor.get_voice_channel(session.ctx)
            if session and session_vc.id == before.channel.id:
                auto_mute = session.auto_mute
                if auto_mute.all:
                    if session.state in [bot_enum.State.POMODORO, bot_enum.State.COUNTDOWN] and \
                            (getattr(session.ctx, 'voice_client', None) or session.ctx.guild.voice_client):
                        print(f"unmuting {member.display_name}")
                        try:
                            await member.edit(mute=False)
                        except HTTPException as e:
                            if e.text == "Target user is not connected to voice.":
                                print("text is",e.text)
                                await session.ctx.channel.send(f"ちょっと待って、{member.mention}！　あなたのサーバミュートが解除できていません。\n一度ボイスチャンネルに再接続してから次のどちらかの手順を選んでください。\n1. `/disableautomute` コマンドを実行する\n2. 別のボイスチャンネルに移動してから通話を離脱する", silent=True)
                            else:
                                print(e.text)

        # 移動後のチャンネルが存在する場合
        if after.channel:
            print(f'{member.display_name} joined the channel {after.channel.name}.')
            session = vc_manager.get_connected_session(str(after.channel.guild.id))
            session_vc = vc_accessor.get_voice_channel(session.ctx)
            if session and session_vc.name == after.channel.name:
                auto_mute = session.auto_mute
                if auto_mute.all:
                    if session.state in [bot_enum.State.POMODORO, bot_enum.State.COUNTDOWN] and \
                            (getattr(session.ctx, 'voice_client', None) or session.ctx.guild.voice_client) and not (member.voice.mute):
                        print(f"muting {member.display_name}")
                        await auto_mute.safe_edit_member(member, unmute=False)
        
async def setup(client):
    await client.add_cog(Subscribe(client))
