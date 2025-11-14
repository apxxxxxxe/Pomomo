import time as t
from asyncio import sleep
import logging

from discord import Colour

from ..voice_client import vc_accessor, vc_manager
from . import session_manager, session_controller
from .Session import Session
from ..utils import player
from ..utils.api_monitor import get_api_monitor
from configs.logging_config import get_logger

logger = get_logger(__name__)


async def handle_connection(session: Session, audio_alert: str):
    try:
        if audio_alert != 'mute':
            # ボイスチャンネルに接続されていない場合、接続を試みる
            await vc_manager.connect(session)
        else:
            # mute モードの場合、ボイスチャンネルから切断し、フラグを設定
            session.is_muted_mode = True
            vc = vc_accessor.get_voice_client(session.ctx)
            if vc:
                await vc.disconnect()
    except Exception as e:
        logger.error(f"Error handling countdown connection: {e}")
        logger.exception("Exception details:")
        raise


async def update_msg(session: Session):
    try:
        timer = session.timer
        timer.remaining = timer.end - t.time()
        if not session.bot_start_msg:
            return
        countdown_msg = session.bot_start_msg
        embed = countdown_msg.embeds[0]
        if timer.remaining < 0:
            embed.colour = Colour.red()
            embed.description = '終了!'
            # mute モードでない場合のみ unmute を実行
            if not getattr(session, 'is_muted_mode', False):
                await session.auto_mute.unmute(session.ctx)
            monitor = get_api_monitor()
            start_time = t.time()
            success = True
            error_msg = None
            
            try:
                await countdown_msg.edit(embed=embed)
            except Exception as edit_error:
                success = False
                error_msg = str(edit_error)
                raise
            finally:
                edit_duration = t.time() - start_time
                logger.debug(f"Countdown final message edit took {edit_duration:.3f}s")
                
                # APIモニタに手動ログを記録
                monitor.log_manual_edit_attempt(
                    operation_type="countdown_final_message_edit",
                    duration=edit_duration,
                    success=success,
                    error_msg=error_msg
                )
            await session.dm.send_dm(embed=embed)
            await player.alert(session)
            await session_controller.end(session)
            return
        embed.description = f'**残り{timer.time_remaining_to_str(hi_rez=True)}**'
        
        # メッセージ編集の実行と監視
        monitor = get_api_monitor()
        start_time = t.time()
        success = True
        error_msg = None
        
        try:
            await countdown_msg.edit(embed=embed)
        except Exception as edit_error:
            success = False
            error_msg = str(edit_error)
            raise
        finally:
            # 編集操作の実行時間をログ出力
            edit_duration = t.time() - start_time
            logger.debug(f"Countdown message edit took {edit_duration:.3f}s")
            
            # APIモニタに手動ログを記録
            monitor.log_manual_edit_attempt(
                operation_type="countdown_message_edit",
                duration=edit_duration,
                success=success,
                error_msg=error_msg
            )
    except Exception as e:
        logger.error(f"Error updating countdown message: {e}")
        logger.exception("Exception details:")


async def start(session: Session):
    try:
        import time
        logger.info(f"Starting countdown for guild {session.ctx.guild.id}")
        session.timer.running = True
        session.timer.end = time.time() + session.timer.remaining
        last_remaining_seconds = -1  # 前回更新時の残り秒数を記録
        while True:
            time_remaining = session.timer.remaining
            await sleep(1)
            session = session_manager.active_sessions.get(session_manager.session_id_from(session.ctx))
            if not (session and
                    session.timer.running and
                    time_remaining == session.timer.remaining):
                break
            
            # タイマーの残り時間を更新
            session.timer.remaining = session.timer.end - time.time()
            
            # 残り時間に応じた更新判定
            remaining_seconds = round(session.timer.remaining)
            remaining_minutes = int(session.timer.remaining / 60)
            should_update = False
            
            if remaining_minutes == session.settings.duration - 1 or remaining_seconds < 60:
                # 開始1分未満または残り時間1分未満の場合: 秒数の1の位が0か5のときのみ更新（0:55, 0:50, ..., 0:05, 0:00）
                should_update = remaining_seconds % 10 == 0 or remaining_seconds % 10 == 5
            else:
                # 1分以上の場合: 秒数が0または30のときのみ更新（1:00, 1:30, 2:00等）
                should_update = remaining_seconds % 60 == 0 or remaining_seconds % 60 == 30
            
            # 更新条件を満たし、かつ前回と異なる秒数の場合のみ更新
            if should_update and remaining_seconds != last_remaining_seconds:
                await update_msg(session)
                last_remaining_seconds = remaining_seconds
    except Exception as e:
        logger.error(f"Error in countdown start: {e}")
        logger.exception("Exception details:")
