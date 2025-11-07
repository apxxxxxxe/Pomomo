import time as t

from ..voice_client import vc_manager
from .Session import Session


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

    # メッセージを更新（詳細情報を含む）
    embed = msg_builder.classwork_embed(session)
    await classwork_msg.edit(embed=embed)
