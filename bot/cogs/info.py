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

    @app_commands.command(name="help", description="ヘルプ情報を表示する")
    @app_commands.describe(command="ヘルプを表示するコマンド名（省略可）")
    async def help(self, interaction: discord.Interaction, command: str = ''):
        help_embed = msg_builder.help_embed(command)
        if help_embed:
            await interaction.response.send_message(embed=help_embed)
        else:
            await interaction.response.send_message('有効なコマンドを入力してください。')

async def setup(client):
    await client.add_cog(Info(client))
