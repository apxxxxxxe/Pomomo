from random import choice

import discord
from discord.ext import commands
from discord import app_commands

from src.session import session_manager
from src.utils import msg_builder
from configs import user_messages as u_msg, bot_enum


class Info(commands.Cog):

    def __init__(self, client):
        self.client = client

    @app_commands.command(name="help", description="Get help information")
    @app_commands.describe(command="ヘルプを表示するコマンド名（省略可）")
    async def help(self, interaction: discord.Interaction, command: str = ''):
        help_embed = msg_builder.help_embed(command)
        if help_embed:
            await interaction.response.send_message(embed=help_embed)
        else:
            await interaction.response.send_message('有効なコマンドを入力してください。')

    @app_commands.command(name="time", description="Show remaining time in current session")
    async def time(self, interaction: discord.Interaction):
        session = await session_manager.get_session_interaction(interaction)
        if session:
            await interaction.response.send_message(f'{session.state}の残り時間：{session.timer.time_remaining_to_str()}！')
        else:
            await interaction.response.send_message('アクティブなセッションがありません。')

    @app_commands.command(name="servers", description="Show server information")
    async def servers(self, interaction: discord.Interaction):
        await interaction.response.send_message(f'Pomomoは{len(self.client.guilds)}のサーバーの {len(session_manager.active_sessions)}個のアクティブセッションで稼働中です！')


async def setup(client):
    await client.add_cog(Info(client))
