import os
import logging

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv, find_dotenv

from configs import config
from configs.logging_config import setup_logging, get_logger
from src.session import session_manager, goal_manager
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
    
    # セッション永続化からの復旧
    try:
        recovered_count = await session_manager.recover_sessions_from_persistence(bot)
        if recovered_count > 0:
            logger.info(f"Recovered {recovered_count} session(s) from persistence")
        else:
            logger.info("No sessions to recover from persistence")
    except Exception as e:
        logger.error(f"Failed to recover sessions from persistence: {e}")
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

@bot.event
async def on_message(message):
    """メッセージイベント処理：botへのメンションを目標として記録"""
    # botのメッセージは無視
    if message.author.bot:
        return
    
    # botがメンションされているかチェック
    if bot.user in message.mentions:
        guild_id = message.guild.id if message.guild else None
        user_id = message.author.id
        
        if guild_id:
            # アクティブセッションがあるかチェック
            session_id = session_manager.session_id_from(message)
            session = session_manager.active_sessions.get(session_id)
            if session:
                # メンション部分を除いた目標テキストを抽出
                goal_text = message.content.replace(f'<@{bot.user.id}>', '').strip()
                if goal_text:
                    # 既存の目標があるかチェック
                    existing_goal = goal_manager.get_goal(guild_id, user_id)
                    
                    goal_manager.set_goal(guild_id, user_id, goal_text)
                    logger.info(f"Goal set for user {user_id}: {goal_text}")
                    
                    # 確認メッセージを送信（上書きの場合は既存目標も表示）
                    if existing_goal:
                        confirmation_msg = f"<@{user_id}> 了解しました。前回の目標 `{existing_goal}` は上書きされます💾"
                    else:
                        confirmation_msg = f"<@{user_id}> 了解しました。応援しています！"
                    
                    try:
                        await message.channel.send(confirmation_msg, silent=True)
                        logger.info(f"Sent confirmation message to user {user_id}")
                    except Exception as e:
                        logger.error(f"Failed to send confirmation message: {e}")
            else:
                # セッションがない場合のメッセージ
                try:
                    no_session_msg = "目標を設定したい場合、まずはセッションを開始してください🍅"
                    await message.channel.send(no_session_msg, silent=True)
                    logger.info(f"Sent no session message to user {user_id}")
                except Exception as e:
                    logger.error(f"Failed to send no session message: {e}")
    
    # 通常のコマンド処理
    await bot.process_commands(message)

@bot.event
async def on_reaction_add(reaction, user):
    """リアクション追加イベント処理：進捗確認メッセージのリアクションに応答"""
    # botのリアクションは無視
    if user.bot:
        return
    
    # 進捗確認メッセージかどうかをチェック（botのembedメッセージで特定のタイトルを含む）
    message = reaction.message
    if (message.author == bot.user and 
        message.embeds and 
        len(message.embeds) > 0 and
        "進捗確認" in message.embeds[0].title):
        
        guild_id = message.guild.id if message.guild else None
        user_id = user.id
        
        if guild_id:
            goal = goal_manager.get_goal(guild_id, user_id)
            if goal:
                # 既にこのメッセージにリアクションしているかチェック
                message_id = message.id
                if goal_manager.has_user_reacted_to_message(guild_id, user_id, message_id):
                    logger.debug(f"User {user_id} already reacted to message {message_id}, ignoring")
                    return
                
                # リアクション記録
                goal_manager.mark_user_reacted_to_message(guild_id, user_id, message_id)
                
                # リアクションに応じた応援メッセージを送信
                emoji = str(reaction.emoji)
                encouragement = goal_manager.get_encouragement_message(emoji)
                
                try:
                    await message.channel.send(f"<@{user_id}> {encouragement}", silent=True)
                    logger.info(f"Sent encouragement to user {user_id} for reaction {emoji}")
                    
                    # 達成リアクション（🏆）の場合は目標を削除
                    if emoji == "🏆":
                        goal_manager.remove_goal(guild_id, user_id)
                        logger.info(f"Goal completed and removed for user {user_id}")
                        
                except Exception as e:
                    logger.error(f"Failed to send encouragement message: {e}")
            else:
                # 進捗確認対象外ユーザーの場合
                message_id = message.id
                if not goal_manager.has_non_goal_user_reacted_to_message(guild_id, user_id, message_id):
                    # 初回リアクションの場合のみメッセージを送信
                    goal_manager.mark_non_goal_user_reacted_to_message(guild_id, user_id, message_id)
                    
                    try:
                        encouragement_msg = f"<@{user_id}> 頑張っていますね！よろしければ目標を教えて下さい！"
                        await message.channel.send(encouragement_msg, silent=True)
                        logger.info(f"Sent goal request message to non-goal user {user_id}")
                    except Exception as e:
                        logger.error(f"Failed to send goal request message: {e}")
                else:
                    logger.debug(f"Non-goal user {user_id} already reacted to message {message_id}, ignoring")

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
    finally:
        # 終了時にアクティブセッションを保存
        try:
            saved_count = await session_manager.save_all_active_sessions()
            if saved_count > 0:
                logger.info(f"Saved {saved_count} active session(s) before shutdown")
            
            # 永続化ストアを閉じる
            from src.persistence.session_store import close_session_store
            close_session_store()
            logger.info("Session store closed")
        except Exception as e:
            logger.error(f"Error during session cleanup: {e}")
            logger.exception("Exception details:")

if __name__ == '__main__':
    import asyncio
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}")
        logger.exception("Exception details:")


