import time as t
from asyncio import sleep

from discord import Colour

from ..voice_client import vc_accessor, vc_manager
from . import session_manager, session_controller
from .Session import Session
from ..utils import player


async def handle_connection(session: Session):
    # ボイスチャンネルに接続されていない場合、接続を試みる
    await vc_manager.connect(session)


async def update_msg(session: Session):
    from ..utils import msg_builder
    
    timer = session.timer
    timer.remaining = timer.end - t.time()
    if not session.bot_start_msg:
        return
    classwork_msg = session.bot_start_msg
    
    if timer.remaining < 0:
        embed = msg_builder.classwork_embed(session)
        embed.colour = Colour.green()
        # ステート表示を終了メッセージに更新
        embed.description = embed.description.replace(f'現在: **{bot_enum.State.get_display_name(session.state)}**', '現在: **終了!**')
        embed.description = embed.description.replace(f'残り時間: **{session.timer.time_remaining_to_str(hi_rez=True)}**', '残り時間: **終了!**')
        
        await classwork_msg.edit(embed=embed)
        await session.dm.send_dm(embed=embed)
        await player.alert(session)
        # classworkは自動で次の状態に遷移
        await transition_to_next_state(session)
        return
    
    # 通常のアップデート（詳細情報を含む）
    embed = msg_builder.classwork_embed(session)
    await classwork_msg.edit(embed=embed)


async def transition_to_next_state(session: Session):
    from configs import bot_enum
    from utils import player
    
    # 現在の状態に応じて次の状態に遷移
    if session.state == bot_enum.State.CLASSWORK:
        session.state = bot_enum.State.CLASSWORK_BREAK
        await session.auto_mute.unmute(session.ctx)
    else:  # CLASSWORK_BREAK
        session.state = bot_enum.State.CLASSWORK
        await session.auto_mute.mute(session.ctx)
    
    # 状態遷移時にアラート音を再生
    await player.alert(session)
    
    # 次の状態用の設定でタイマーをリセット
    session.timer.set_time_remaining()
    await session_controller.resume(session)


async def start(session: Session):
    import time
    session.timer.running = True
    session.timer.end = time.time() + session.timer.remaining
    
    # セッション開始時刻を記録
    session.current_session_start_time = time.time()
    
    while True:
        time_remaining = session.timer.remaining
        await sleep(1)
        session = session_manager.active_sessions.get(session_manager.session_id_from(session.ctx))
        if not (session and
                session.timer.running and
                time_remaining == session.timer.remaining):
            break
        await update_msg(session)
