from discord import VoiceChannel

from configs import user_messages as u_msg
from ..session.Session import Session

connected_sessions = {}


async def connect(session: Session):
    ctx = session.ctx
    # Handle both Interaction and Context objects
    voice_client = getattr(ctx, 'voice_client', None) or ctx.guild.voice_client
    
    if voice_client and get_connected_session(voice_client.channel):
        if hasattr(ctx, 'send'):
            await ctx.send(u_msg.ACTIVE_SESSION_EXISTS_ERR)
        else:
            await ctx.response.send_message(u_msg.ACTIVE_SESSION_EXISTS_ERR)
        return
    
    # Get user voice channel
    user_voice = ctx.author.voice if hasattr(ctx, 'author') else ctx.user.voice
    voice_client = await user_voice.channel.connect()
    await ctx.guild.get_member((ctx.client if hasattr(ctx, 'client') else ctx.bot).user.id).edit(deafen=True)
    if voice_client:
        connected_sessions[voice_channel_id_from(voice_client.channel)] = session
    return True


async def disconnect(session: Session):
    vc_id = voice_channel_id_from((getattr(session.ctx, 'voice_client', None) or session.ctx.guild.voice_client).channel)
    await (getattr(session.ctx, 'voice_client', None) or session.ctx.guild.voice_client).disconnect()
    connected_sessions.pop(vc_id)


def get_connected_session(vc: VoiceChannel) -> Session:
    return connected_sessions.get(voice_channel_id_from(vc))


def voice_channel_id_from(vc: VoiceChannel) -> str:
    return str(vc.guild.id) + str(vc.id)
