import logging

from discord import VoiceChannel

from configs import user_messages as u_msg
from ..session.Session import Session
from configs.logging_config import get_logger

logger = get_logger(__name__)

connected_sessions = {}


async def connect(session: Session):
    try:
        ctx = session.ctx
        guild_id = str(ctx.guild.id)
        logger.debug(f"Attempting to connect to voice channel for guild {guild_id}")
        
        # Handle both Interaction and Context objects
        voice_client = getattr(ctx, 'voice_client', None) or ctx.guild.voice_client
        
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
            connected_sessions[str(ctx.guild.id)] = session
            logger.info(f"Connected to voice channel {user_voice.channel.name} for guild {guild_id}")
        return True
    except Exception as e:
        logger.error(f"Error connecting to voice channel: {e}")
        logger.exception("Exception details:")
        return False


async def disconnect(session: Session):
    try:
        guild_id = str(session.ctx.guild.id)
        logger.debug(f"Disconnecting from voice channel for guild {guild_id}")
        
        voice_client = getattr(session.ctx, 'voice_client', None) or session.ctx.guild.voice_client
        if voice_client:
            await voice_client.disconnect()
            logger.info(f"Disconnected from voice channel for guild {guild_id}")
        
        if guild_id in connected_sessions:
            connected_sessions.pop(guild_id)
    except Exception as e:
        logger.error(f"Error disconnecting from voice channel: {e}")
        logger.exception("Exception details:")


def get_connected_session(guild_id: str) -> Session:
    return connected_sessions.get(guild_id)


# Removed: voice_channel_id_from function is no longer needed since we use guild IDs directly
