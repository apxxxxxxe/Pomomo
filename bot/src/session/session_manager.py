import asyncio
import random
import time as t

import discord
from discord import TextChannel
from discord.ext.commands import Context

from .Session import Session
from ..voice_client import vc_accessor
from configs import config, user_messages as u_msg
from configs.logging_config import get_logger

logger = get_logger(__name__)

active_sessions = {}
# ギルドごとのセッション操作のロック
session_locks = {}


async def activate(session: Session):
    guild_id = session_id_from(session.ctx)
    
    # ギルドごとのロックを取得または作成
    if guild_id not in session_locks:
        session_locks[guild_id] = asyncio.Lock()
    
    lock = session_locks[guild_id]
    
    async with lock:
        active_sessions[guild_id] = session
        logger.debug(f"Session activated for guild {guild_id}")


async def deactivate(session: Session):
    guild_id = session_id_from(session.ctx)
    
    # ギルドごとのロックを取得または作成  
    if guild_id not in session_locks:
        session_locks[guild_id] = asyncio.Lock()
    
    lock = session_locks[guild_id]
    
    async with lock:
        if guild_id in active_sessions:
            active_sessions.pop(guild_id)
            logger.debug(f"Session deactivated for guild {guild_id}")
        else:
            logger.warning(f"Attempted to deactivate non-existent session for guild {guild_id}")


async def get_session(ctx: Context) -> Session:
    session = active_sessions.get(session_id_from(ctx))
    if not session:
        await ctx.send(u_msg.NO_ACTIVE_SESSION_ERR)
    return session


async def get_session_interaction(interaction: discord.Interaction) -> Session:
    session = active_sessions.get(session_id_from(interaction))
    return session


def session_id_from(ctx) -> str:
    return str(ctx.guild.id)


async def kill_if_idle(session: Session):
    ctx = session.ctx
    
    # Skip idle check for Interaction-based sessions for now
    if hasattr(ctx, 'client'):  # This is an Interaction
        return False
        
    if not vc_accessor.get_voice_channel(ctx) or\
            len(vc_accessor.get_true_members_in_voice_channel(ctx)) == 0:
        await ctx.invoke(ctx.bot.get_command('stop'))
        return True
    if t.time() < session.timeout:
        return
    else:
        def check(reaction, user):
            return reaction.emoji == '👍' and user != ctx.bot.user
        msg = await ctx.channel.send('まだいますか？')
        await msg.add_reaction('👍')
        try:
            await ctx.bot.wait_for('reaction_add', check=check, timeout=60)
        except asyncio.TimeoutError:
            await ctx.invoke(ctx.bot.get_command('stop'))
        else:
            await ctx.send(random.choice(u_msg.STILL_THERE))
            if session.timer.running:
                session.timeout = t.time() + config.TIMEOUT_SECONDS
            else:
                session.timeout = t.time() + config.PAUSE_TIMEOUT_SECONDS
