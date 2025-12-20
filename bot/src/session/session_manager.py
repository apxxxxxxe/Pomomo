import asyncio
import random
import time as t

import discord
from discord import TextChannel
from discord.ext.commands import Context

from .Session import Session
from ..voice_client import vc_accessor
from ..persistence.session_store import get_session_store
from configs import config, user_messages as u_msg
from configs.logging_config import get_logger

logger = get_logger(__name__)

active_sessions = {}
# ギルドごとのセッション操作のロック
session_locks = {}
# 永続化が有効かどうか
_persistence_enabled = True


async def activate(session: Session):
    guild_id = session_id_from(session.ctx)
    
    # ギルドごとのロックを取得または作成
    if guild_id not in session_locks:
        session_locks[guild_id] = asyncio.Lock()
    
    lock = session_locks[guild_id]
    
    async with lock:
        active_sessions[guild_id] = session
        logger.debug(f"Session activated for guild {guild_id}")
        
        # 永続化
        if _persistence_enabled:
            try:
                store = get_session_store()
                if store.save_session(int(guild_id), session):
                    logger.debug(f"Session persisted for guild {guild_id}")
                else:
                    logger.warning(f"Failed to persist session for guild {guild_id}")
            except Exception as e:
                logger.error(f"Session persistence error for guild {guild_id}: {e}")


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
            
            # 永続化ストアからも削除
            if _persistence_enabled:
                try:
                    store = get_session_store()
                    if store.delete_session(int(guild_id)):
                        logger.debug(f"Persisted session deleted for guild {guild_id}")
                    else:
                        logger.warning(f"Failed to delete persisted session for guild {guild_id}")
                except Exception as e:
                    logger.error(f"Session persistence deletion error for guild {guild_id}: {e}")
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
    
    # Skip if ctx is None (recovered sessions without context)
    if ctx is None:
        return False
    
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


async def recover_sessions_from_persistence(bot):
    """
    起動時に永続化されたセッションを復旧
    
    Args:
        bot: Discordボットインスタンス
    
    Returns:
        復旧されたセッション数
    """
    if not _persistence_enabled:
        logger.info("Persistence disabled, skipping session recovery")
        return 0
    
    try:
        store = get_session_store()
        persisted_sessions = store.load_all_sessions()
        
        recovered_count = 0
        for guild_id, session in persisted_sessions.items():
            try:
                # ギルドが存在するか確認
                guild = bot.get_guild(guild_id)
                if not guild:
                    logger.warning(f"Guild {guild_id} not found, skipping session recovery")
                    # 存在しないギルドのセッションは削除
                    store.delete_session(guild_id)
                    continue
                
                # セッションをメモリに復旧（ctxは後で設定される）
                active_sessions[str(guild_id)] = session
                recovered_count += 1
                logger.info(f"Session recovered for guild {guild_id}")
                
            except Exception as e:
                logger.error(f"Failed to recover session for guild {guild_id}: {e}")
        
        # 期限切れセッションをクリーンアップ
        cleaned_count = store.cleanup_expired_sessions(max_age_hours=24)
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} expired sessions")
        
        logger.info(f"Session recovery complete: {recovered_count} sessions recovered")
        return recovered_count
        
    except Exception as e:
        logger.error(f"Session recovery failed: {e}")
        return 0


def enable_persistence():
    """永続化を有効化"""
    global _persistence_enabled
    _persistence_enabled = True
    logger.info("Session persistence enabled")


def disable_persistence():
    """永続化を無効化"""
    global _persistence_enabled
    _persistence_enabled = False
    logger.info("Session persistence disabled")


def is_persistence_enabled() -> bool:
    """永続化が有効かどうかを確認"""
    return _persistence_enabled


async def save_all_active_sessions():
    """
    現在アクティブな全セッションを永続化
    
    Returns:
        保存成功したセッション数
    """
    if not _persistence_enabled:
        return 0
    
    saved_count = 0
    store = get_session_store()
    
    for guild_id, session in active_sessions.items():
        try:
            if store.save_session(int(guild_id), session):
                saved_count += 1
                logger.debug(f"Session saved for guild {guild_id}")
            else:
                logger.warning(f"Failed to save session for guild {guild_id}")
        except Exception as e:
            logger.error(f"Session save error for guild {guild_id}: {e}")
    
    logger.info(f"Bulk session save complete: {saved_count}/{len(active_sessions)} sessions saved")
    return saved_count


async def update_session_persistence(session: Session):
    """
    セッション状態の変更時に永続化を更新
    セッション中の状態変更（タイマー、Stats更新など）で使用
    
    Args:
        session: 更新するセッション
    """
    if not _persistence_enabled or not session.ctx:
        return
    
    guild_id = session_id_from(session.ctx)
    
    try:
        store = get_session_store()
        if store.save_session(int(guild_id), session):
            logger.debug(f"Session state updated in persistence for guild {guild_id}")
        else:
            logger.warning(f"Failed to update session persistence for guild {guild_id}")
    except Exception as e:
        logger.error(f"Session persistence update error for guild {guild_id}: {e}")


def get_persistence_stats():
    """
    永続化統計情報を取得
    
    Returns:
        統計情報の辞書
    """
    try:
        store = get_session_store()
        return {
            'enabled': _persistence_enabled,
            'total_persisted': store.get_session_count(),
            'active_sessions': len(active_sessions),
            'db_path': store.db_path
        }
    except Exception as e:
        logger.error(f"Failed to get persistence stats: {e}")
        return {
            'enabled': _persistence_enabled,
            'total_persisted': 0,
            'active_sessions': len(active_sessions),
            'error': str(e)
        }
