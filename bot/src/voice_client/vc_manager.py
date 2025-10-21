from discord import VoiceChannel

from configs import user_messages as u_msg
from ..session.Session import Session

connected_sessions = {}


async def connect(session: Session):
    ctx = session.ctx
    # Handle both Interaction and Context objects
    voice_client = getattr(ctx, 'voice_client', None) or ctx.guild.voice_client
    
    # Check if there's already an active session in this guild
    guild_id = str(ctx.guild.id)
    if guild_id in connected_sessions:
        if hasattr(ctx, 'send'):
            await ctx.send(u_msg.ACTIVE_SESSION_EXISTS_ERR)
        else:
            await ctx.response.send_message(u_msg.ACTIVE_SESSION_EXISTS_ERR)
        return
    
    # Get user voice channel
    user_voice = ctx.author.voice if hasattr(ctx, 'author') else ctx.user.voice
    voice_client = await user_voice.channel.connect()
    # await ctx.guild.get_member((ctx.client if hasattr(ctx, 'client') else ctx.bot).user.id).edit(deafen=True)
    if voice_client:
        connected_sessions[str(ctx.guild.id)] = session
    return True


async def disconnect(session: Session):
    guild_id = str(session.ctx.guild.id)
    await (getattr(session.ctx, 'voice_client', None) or session.ctx.guild.voice_client).disconnect()
    connected_sessions.pop(guild_id)


def get_connected_session(guild_id: str) -> Session:
    return connected_sessions.get(guild_id)


# Removed: voice_channel_id_from function is no longer needed since we use guild IDs directly
