import time as t

from discord import Colour

from .Session import Session


async def update_msg(session: Session):
    timer = session.timer
    timer.remaining = timer.end - t.time()
    if not session.bot_start_msg:
        return
    
    pomodoro_msg = session.bot_start_msg
    embed = pomodoro_msg.embeds[0]
    
    if timer.remaining < 0:
        # タイマー終了時の処理はsession_controllerで行われるため、ここでは何もしない
        return
    
    # 残り時間をdescriptionの末尾に追加
    original_description = embed.description or ""
    
    # 既に残り時間が含まれている場合は除去
    if ' - 残り' in original_description:
        # 最後の " - 残りXX:XX" 部分を除去
        parts = original_description.split(' - 残り')
        if len(parts) > 1:
            original_description = parts[0]
    
    # 新しい残り時間を追加
    embed.description = f'{original_description} - 残り{timer.time_remaining_to_str(hi_rez=True)}'
    await pomodoro_msg.edit(embed=embed)
