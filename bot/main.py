import os
import logging

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv, find_dotenv

from configs import config
from configs.logging_config import setup_logging, get_logger
from src.session import session_manager
from src.utils.api_monitor import setup_api_monitoring
from src.utils.aiohttp_hook import setup_aiohttp_monitoring

# ロギングの設定
setup_logging()
logger = get_logger(__name__)

intents = discord.Intents.default()
intents.typing = False
intents.members = True
intents.message_content = True

try:
    env_path = find_dotenv(raise_error_if_not_found=True)
    load_dotenv(env_path)
    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        raise ValueError("DISCORD_TOKEN not found in environment variables")
    logger.info(f"Loaded .env file from: {env_path}")
except Exception as e:
    logger.critical(f"Failed to load environment variables: {e}")
    raise
bot = commands.Bot(command_prefix=config.CMD_PREFIX, help_command=None, intents=intents)

@tasks.loop(minutes=30)
async def kill_idle_sessions():
    try:
        logger.debug("Running kill_idle_sessions task")
        for session in session_manager.active_sessions.values():
            try:
                await session_manager.kill_if_idle(session)
            except Exception as e:
                logger.error(f"Error killing idle session {session.ctx.guild.id}: {e}")
    except Exception as e:
        logger.error(f"Error in kill_idle_sessions task: {e}")
        logger.exception("Exception details:")

@bot.event
async def on_ready():
    logger.info(f'{bot.user} has connected to Discord!')
    logger.info(f'Commands in tree: {len(bot.tree.get_commands())}')
    for cmd in bot.tree.get_commands():
        logger.debug(f'- {cmd.name}: {cmd.description}')
    try:
        synced = await bot.tree.sync()
        logger.info(f'Synced {len(synced)} command(s)')
        for cmd in synced:
            logger.debug(f'Synced: {cmd.name}')
    except Exception as e:
        logger.error(f'Failed to sync commands: {e}')
        logger.exception("Exception details:")
    
    try:
        kill_idle_sessions.start()
        logger.info("Started kill_idle_sessions task")
    except Exception as e:
        logger.error(f"Failed to start kill_idle_sessions task: {e}")
    
    # APIレスポンスヘッダ監視の設定
    try:
        # まず従来のAPI監視を設定（HTTPフックは無効）
        setup_api_monitoring(bot, enable_hook=False)
        logger.info("API monitoring setup completed")
        
        # aiohttpレベルでのフックを試みる
        if setup_aiohttp_monitoring(bot):
            logger.info("aiohttp level monitoring enabled")
        else:
            logger.warning("aiohttp monitoring not available - using manual logging only")
    except Exception as e:
        logger.error(f"Failed to setup API monitoring: {e}")

async def load_extensions():
    cogs_to_load = ['cogs.info', 'cogs.control', 'cogs.subscribe']
    for cog in cogs_to_load:
        try:
            await bot.load_extension(cog)
            logger.info(f'Loaded {cog}')
        except Exception as e:
            logger.error(f'Error loading {cog}: {e}')
            logger.exception("Exception details:")

async def main():
    try:
        await load_extensions()
        logger.info("Starting bot...")
        await bot.start(TOKEN)
    except Exception as e:
        logger.critical(f"Failed to start bot: {e}")
        logger.exception("Exception details:")
        raise

if __name__ == '__main__':
    import asyncio
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}")
        logger.exception("Exception details:")


