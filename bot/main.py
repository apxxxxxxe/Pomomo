import os

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv, find_dotenv

from configs import config
from src.session import session_manager

intents = discord.Intents.default()
intents.typing = False
intents.members = True
intents.message_content = True

env_path = find_dotenv(raise_error_if_not_found=True)
load_dotenv(env_path)
TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    raise ValueError("DISCORD_TOKEN not found in environment variables")
print("Loaded .env file from:", env_path)
bot = commands.Bot(command_prefix=config.CMD_PREFIX, help_command=None, intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Commands in tree: {len(bot.tree.get_commands())}')
    for cmd in bot.tree.get_commands():
        print(f'- {cmd.name}: {cmd.description}')
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} command(s)')
        for cmd in synced:
            print(f'Synced: {cmd.name}')
    except Exception as e:
        print(f'Failed to sync commands: {e}')
        import traceback
        traceback.print_exc()
    kill_idle_sessions.start()

async def load_extensions():
    try:
        await bot.load_extension('cogs.info')
        print('Loaded cogs.info')
        await bot.load_extension('cogs.control')
        print('Loaded cogs.control')
        await bot.load_extension('cogs.subscribe')
        print('Loaded cogs.subscribe')
    except Exception as e:
        print(f'Error loading cogs: {e}')
        import traceback
        traceback.print_exc()

async def main():
    await load_extensions()
    await bot.start(TOKEN)

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())


@tasks.loop(minutes=30)
async def kill_idle_sessions():
    for session in session_manager.active_sessions.values():
        await session_manager.kill_if_idle(session)


