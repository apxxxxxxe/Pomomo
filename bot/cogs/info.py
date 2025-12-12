from random import choice
import logging

import discord
from discord.ext import commands
from discord import app_commands

from src.session import session_manager
from src.utils import msg_builder
from configs import user_messages as u_msg, bot_enum
from configs.logging_config import get_logger

logger = get_logger(__name__)


class Info(commands.Cog):

    def __init__(self, client):
        self.client = client

    @app_commands.command(name="help", description="ヘルプ情報を表示する")
    @app_commands.describe(command="ヘルプを表示するコマンド名（省略可）")
    async def help(self, interaction: discord.Interaction, command: str = ''):
        help_embed = msg_builder.help_embed(command)
        if help_embed:
            await interaction.response.send_message(embed=help_embed, ephemeral=True)
        else:
            await interaction.response.send_message(u_msg.HELP_COMMAND_ERROR, ephemeral=True)

    @help.error
    async def help_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        logger.error(f"Help command error for user {interaction.user}: {type(error).__name__}")
        
        try:
            if isinstance(error, app_commands.CommandInvokeError):
                logger.exception("CommandInvokeError in help command:", exc_info=error)
                # システムエラーとして扱う
                if not interaction.response.is_done():
                    await interaction.response.send_message(u_msg.HELP_COMMAND_ERROR, ephemeral=True)
                else:
                    await interaction.followup.send(u_msg.HELP_COMMAND_ERROR, ephemeral=True)
            else:
                logger.error(f"Unhandled error type in help: {type(error).__name__}")
                logger.exception("Exception details:", exc_info=error)
                # その他のエラー
                if not interaction.response.is_done():
                    await interaction.response.send_message(u_msg.HELP_COMMAND_ERROR, ephemeral=True)
                else:
                    await interaction.followup.send(u_msg.HELP_COMMAND_ERROR, ephemeral=True)
        except Exception as e:
            logger.error(f"Error in help error handler: {e}")
            logger.exception("Exception details:")

async def setup(client):
    await client.add_cog(Info(client))
