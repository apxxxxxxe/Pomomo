from asyncio import sleep

from discord import FFmpegPCMAudio, PCMVolumeTransformer

from configs import bot_enum
from ..session.Session import Session


async def alert(session: Session):
    vc = getattr(session.ctx, 'voice_client', None) or session.ctx.guild.voice_client
    if not vc:
        return

    if session.state == bot_enum.State.COUNTDOWN:
        path = bot_enum.AlertPath.POMO_END
    elif session.state == bot_enum.State.POMODORO:
        path = bot_enum.AlertPath.POMO_START
    elif session.state == bot_enum.State.LONG_BREAK:
        path = bot_enum.AlertPath.LONG_BREAK_START
    else:  # SHORT_BREAK
        path = bot_enum.AlertPath.POMO_START
    source = PCMVolumeTransformer(FFmpegPCMAudio(path, executable='ffmpeg'),
                                  volume=0.1)
    if vc.is_playing():
        vc.stop()
    vc.play(source)
    while vc.is_playing():
        await sleep(1)
