import random

from discord import Embed, Colour

from .Session import Session
from ..utils import msg_builder
from configs import user_messages as u_msg


async def send_start_msg(session: Session):
    embed = msg_builder.settings_embed(session)
    message = random.choice(u_msg.GREETINGS)
    
    if hasattr(session.ctx, 'send'):  # Context
        session.bot_start_msg = await session.ctx.send(message, embed=embed)
    else:  # Interaction
        if not session.ctx.response.is_done():
            await session.ctx.response.send_message(message, embed=embed)
            session.bot_start_msg = await session.ctx.original_response()
        else:
            session.bot_start_msg = await session.ctx.followup.send(message, embed=embed, wait=True, ephemeral=False)
    await session.bot_start_msg.pin()


async def send_countdown_msg(session: Session, title: str):
    title += '\u2800' * max((18 - len(title)), 0)
    embed = Embed(title=title, description=f'残り{session.timer.time_remaining_to_str()}', colour=Colour.green())
    
    if hasattr(session.ctx, 'send'):  # Context
        session.bot_start_msg = await session.ctx.send(embed=embed)
    else:  # Interaction
        if not session.ctx.response.is_done():
            await session.ctx.response.send_message(embed=embed)
            session.bot_start_msg = await session.ctx.original_response()
        else:
            session.bot_start_msg = await session.ctx.followup.send(embed=embed, wait=True, ephemeral=False)
    print("countdown message sent")
    await session.bot_start_msg.pin()
