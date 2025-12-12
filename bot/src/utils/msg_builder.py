from discord import Embed, Colour

from configs import config, help_info, bot_enum
from ..Stats import Stats
from ..session.Session import Session


def settings_embed(session: Session) -> Embed:
    import time
    
    settings = session.settings
    settings_str = f'作業時間: {settings.duration} 分\n' \
               f'短い休憩: {settings.short_break} 分\n' \
               f'長い休憩: {settings.long_break} 分\n' \
               f'インターバル: {settings.intervals}  ({settings.intervals} 回目の作業後に長い休憩)'
    
    # 残り時間表示を追加
    if session.timer and session.timer.remaining > 0:
        # 総進捗秒数を計算（過去完了分 + 現在セッション進捗）
        total_seconds = session.stats.seconds_completed
        
        # 現在セッションの経過時間を計算（作業時間のみ）
        if session.timer.running and session.state == bot_enum.State.POMODORO:
            # セッション総時間 - 残り時間 = 経過時間（作業時間のみ）
            session_total_duration = session.settings.duration * 60
            
            current_remaining = session.timer.end - time.time()
            current_session_elapsed = session_total_duration - current_remaining
            current_session_elapsed = max(0, round(current_session_elapsed))  # 四捨五入を使用
            total_seconds += current_session_elapsed
        
        # 秒数を「分秒」形式に変換
        def seconds_to_min_sec_str(seconds):
            if seconds < 60:
                return f'{seconds}秒'
            else:
                minutes = seconds // 60
                remaining_seconds = seconds % 60
                if remaining_seconds == 0:
                    return f'{minutes}分'
                else:
                    return f'{minutes}分{remaining_seconds}秒'
        
        progress_str = seconds_to_min_sec_str(total_seconds)
        settings_str += f'\n\n現在: **{bot_enum.State.get_display_name(session.state)}**\n残り時間: **{session.timer.time_remaining_to_str(hi_rez=True)}**\n累計サイクル数: **{session.stats.pomos_completed}**\n累計作業時間: **{progress_str}**'
    
    embed = Embed(title='作業セッション', description=settings_str, colour=Colour.orange())

    vc = getattr(session.ctx, 'voice_client', None) or session.ctx.guild.voice_client
    if vc:
        footer = f'{vc.channel.name} ボイスチャンネルに接続中'
        if session.auto_mute.all:
            footer += '\nAuto-mute is on'
        embed.set_footer(text=footer)

    return embed

def classwork_embed(session: Session) -> Embed:
    import time
    
    # CLASSWORKセッションの基本情報（動的時間設定）
    work_time = session.settings.duration
    break_time = session.settings.short_break
    settings_str = f'作業時間: {work_time} 分\n' \
               f'休憩時間: {break_time} 分'
    
    # 残り時間表示を追加
    if session.timer and session.timer.remaining > 0:
        # 総進捗秒数を計算（過去完了分 + 現在セッション進捗）
        total_seconds = session.stats.seconds_completed
        
        # 現在セッションの経過時間を計算（作業時間のみ）
        if session.timer.running and session.state == bot_enum.State.CLASSWORK:
            # セッション総時間 - 残り時間 = 経過時間（作業時間のみ）
            session_total_duration = work_time * 60  # 動的作業時間
            
            current_remaining = session.timer.end - time.time()
            current_session_elapsed = session_total_duration - current_remaining
            current_session_elapsed = max(0, round(current_session_elapsed))  # 四捨五入を使用
            total_seconds += current_session_elapsed
        
        # 秒数を「分秒」形式に変換
        def seconds_to_min_sec_str(seconds):
            if seconds < 60:
                return f'{seconds}秒'
            else:
                minutes = seconds // 60
                remaining_seconds = seconds % 60
                if remaining_seconds == 0:
                    return f'{minutes}分'
                else:
                    return f'{minutes}分{remaining_seconds}秒'
        
        progress_str = seconds_to_min_sec_str(total_seconds)
        
        settings_str += f'\n\n現在: **{bot_enum.State.get_display_name(session.state)}**\n残り時間: **{session.timer.time_remaining_to_str(hi_rez=True)}**\n累計サイクル数: **{session.stats.pomos_completed}**\n累計作業時間: **{progress_str}**'
    
    embed = Embed(title='作業セッション', description=settings_str, colour=Colour.orange())

    vc = getattr(session.ctx, 'voice_client', None) or session.ctx.guild.voice_client
    if vc:
        footer = f'{vc.channel.name} ボイスチャンネルに接続中'
        if session.auto_mute.all:
            footer += '\nAuto-mute is on'
        embed.set_footer(text=footer)

    return embed


def help_embed(for_command) -> Embed:
    if for_command == '':
        embed = Embed(title='ヘルプメニュー', description=help_info.SUMMARY, colour=Colour.blue())
        for cmds_key, cmds_dict in help_info.COMMANDS.items():
            values = ''
            for value in cmds_dict.values():
                values += f'{value[0]}\n'
            embed.add_field(name=cmds_key, value=values, inline=False)
        more_info = f'`/help [コマンド名]` で特定のコマンドについて詳しい説明が見れます'
        embed.add_field(name='\u200b', value=more_info, inline=False)
        return embed
    else:
        if for_command.startswith('/'):
            for_command = for_command[1:]
        for cmds_key, cmds_dict in help_info.COMMANDS.items():
            cmd_info = cmds_dict.get(for_command)
            if cmd_info:
                return Embed(title=cmd_info[1], description=cmd_info[2], colour=Colour.blue())
        return Embed(title='Error', description='No help found for that command.', colour=Colour.red())


def stats_msg(stats: Stats, session=None):
    import time
    
    pomo_str = 'サイクル'
    total_seconds = stats.seconds_completed
    
    # 作業中の場合、現在の経過時間も含める
    if session and session.current_session_start_time:
        if session.state == bot_enum.State.POMODORO or session.state == bot_enum.State.CLASSWORK:
            current_elapsed = int(time.time() - session.current_session_start_time)
            total_seconds += current_elapsed
    
    # 秒数を時間、分、秒に変換
    hours = total_seconds // 3600
    remaining_seconds = total_seconds % 3600
    minutes = remaining_seconds // 60
    seconds = remaining_seconds % 60
    
    # 時間表示文字列を構築
    time_completed_str = ''
    if hours > 0:
        time_completed_str += f'{hours}時間'
        if minutes > 0:
            time_completed_str += f'{minutes}分'
    elif minutes > 0:
        time_completed_str += f'{minutes}分'
        if seconds > 0:
            time_completed_str += f'{seconds}秒'
    else:
        if total_seconds == 1:
            time_completed_str = '1秒'
        else:
            time_completed_str = f'{total_seconds}秒'
    
    return f'{stats.pomos_completed}{pomo_str}({time_completed_str})'
