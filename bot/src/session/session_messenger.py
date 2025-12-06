import logging
import random

from discord import Embed, Colour

from .Session import Session
from configs.logging_config import get_logger
from configs import user_messages as u_msg

logger = get_logger(__name__)


async def send_countdown_msg(session: Session, title: str):
    # 開始メッセージを送信（ピン留めなし）
    start_message = f'> -# {session.ctx.user.display_name} さんが`/countdown`を使用しました'
    
    if hasattr(session.ctx, 'send'):  # Context
        await session.ctx.send(start_message, silent=True)
    else:  # Interaction
        if not session.ctx.response.is_done():
            await session.ctx.response.send_message(start_message, silent=True)
        else:
            await session.ctx.delete_original_response()
            await session.ctx.channel.send(start_message, silent=True)
    
    # タイマー用のembedメッセージを別途送信
    title += '\u2800' * max((18 - len(title)), 0)
    embed = Embed(title=title, description=f'残り{session.timer.time_remaining_to_str()}', colour=Colour.green())
    session.bot_start_msg = await session.ctx.channel.send(embed=embed, silent=True)
    
    logger.info(f"Countdown message sent for guild {session.ctx.guild.id}")

async def send_classwork_msg(session: Session):
    from ..utils import msg_builder
    
    # 開始メッセージを送信（ピン留めなし）
    start_message = f'> -# {session.ctx.user.display_name} さんが`/start`を使用しました'
    
    if hasattr(session.ctx, 'send'):  # Context
        await session.ctx.send(start_message, silent=True)
    else:  # Interaction
        if not session.ctx.response.is_done():
            await session.ctx.response.send_message(start_message, silent=True)
        else:
            await session.ctx.delete_original_response()
            await session.ctx.channel.send(start_message, silent=True)
    
    # タイマー用のembedメッセージを別途送信
    embed = msg_builder.classwork_embed(session)
    timer_message = f'{random.choice(u_msg.GREETINGS)}'
    session.bot_start_msg = await session.ctx.channel.send(timer_message, embed=embed, silent=True)
    
    logger.info(f"Classwork message sent for guild {session.ctx.guild.id}")

async def send_pomodoro_msg(session: Session):
    """
    ポモドーロセッション開始メッセージを送信する
    """
    from ..utils import msg_builder
    
    # 開始メッセージを送信（ピン留めなし）
    start_message = f'> -# {session.ctx.user.display_name} さんが`/pomodoro`を使用しました'
    await session.ctx.delete_original_response()
    await session.ctx.channel.send(start_message, silent=True)
    
    # タイマー用のembedメッセージを別途送信
    embed = msg_builder.settings_embed(session)
    timer_message = f'{random.choice(u_msg.GREETINGS)}'
    session.bot_start_msg = await session.ctx.channel.send(timer_message, embed=embed, silent=True)
    
    logger.info(f"Pomodoro message sent for guild {session.ctx.guild.id}")
