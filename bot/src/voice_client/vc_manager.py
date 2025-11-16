import logging
import asyncio

from discord import VoiceChannel

from configs import user_messages as u_msg
from ..session.Session import Session
from configs.logging_config import get_logger

logger = get_logger(__name__)

connected_sessions = {}
# ギルドごとの接続/切断操作のロック
connection_locks = {}


async def connect(session: Session):
    ctx = session.ctx
    guild_id = str(ctx.guild.id)
    
    # ギルドごとのロックを取得または作成
    if guild_id not in connection_locks:
        connection_locks[guild_id] = asyncio.Lock()
    
    lock = connection_locks[guild_id]
    
    # ロックの取得を試みる（タイムアウト付き）
    try:
        async with asyncio.timeout(1.0):  # 1秒でタイムアウト
            async with lock:
                logger.debug(f"Attempting to connect to voice channel for guild {guild_id}")
                
                # Handle both Interaction and Context objects
                voice_client = getattr(ctx, 'voice_client', None) or ctx.guild.voice_client
                
                # 既にボイスクライアントが存在する場合は接続済みとみなす
                if voice_client and voice_client.is_connected():
                    logger.info(f"Already connected to voice channel for guild {guild_id}")
                    connected_sessions[guild_id] = session
                    return True
                
                # Check if there's already an active session in this guild
                if guild_id in connected_sessions:
                    logger.warning(f"Active session already exists for guild {guild_id}")
                    if hasattr(ctx, 'send'):
                        await ctx.send(u_msg.ACTIVE_SESSION_EXISTS_ERR)
                    else:
                        await ctx.response.send_message(u_msg.ACTIVE_SESSION_EXISTS_ERR)
                    return False
                
                # Get user voice channel
                user_voice = ctx.author.voice if hasattr(ctx, 'author') else ctx.user.voice
                if not user_voice or not user_voice.channel:
                    logger.warning(f"User not in voice channel for guild {guild_id}")
                    return False
                    
                voice_client = await user_voice.channel.connect()
                # await ctx.guild.get_member((ctx.client if hasattr(ctx, 'client') else ctx.bot).user.id).edit(deafen=True)
                if voice_client:
                    connected_sessions[guild_id] = session
                    logger.info(f"Connected to voice channel {user_voice.channel.name} for guild {guild_id}")
                return True
                
    except asyncio.TimeoutError:
        logger.warning(f"Connection attempt timed out for guild {guild_id} - another operation in progress")
        return False
    except Exception as e:
        logger.error(f"Error connecting to voice channel: {e}")
        logger.exception("Exception details:")
        return False


async def disconnect(session: Session):
    guild_id = str(session.ctx.guild.id)
    
    # ギルドごとのロックを取得または作成
    if guild_id not in connection_locks:
        connection_locks[guild_id] = asyncio.Lock()
    
    lock = connection_locks[guild_id]
    
    try:
        async with asyncio.timeout(1.0):  # 1秒でタイムアウト
            async with lock:
                logger.debug(f"Disconnecting from voice channel for guild {guild_id}")
                
                voice_client = getattr(session.ctx, 'voice_client', None) or session.ctx.guild.voice_client
                if voice_client:
                    await voice_client.disconnect()
                    logger.info(f"Disconnected from voice channel for guild {guild_id}")
                
                if guild_id in connected_sessions:
                    connected_sessions.pop(guild_id, None)  # popにデフォルト値を設定してKeyErrorを回避
                    
    except asyncio.TimeoutError:
        logger.warning(f"Disconnect attempt timed out for guild {guild_id} - another operation in progress")
    except Exception as e:
        logger.error(f"Error disconnecting from voice channel: {e}")
        logger.exception("Exception details:")


def get_connected_session(guild_id: str) -> Session:
    return connected_sessions.get(guild_id)


# Removed: voice_channel_id_from function is no longer needed since we use guild IDs directly
