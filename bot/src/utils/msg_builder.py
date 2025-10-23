from discord import Embed, Colour

from configs import config, help_info
from ..Stats import Stats
from ..session.Session import Session


def settings_embed(session: Session) -> Embed:
    settings = session.settings
    settings_str = f'作業時間: {settings.duration} 分\n' \
               f'短い休憩: {settings.short_break} 分\n' \
               f'長い休憩: {settings.long_break} 分\n' \
               f'インターバル: {settings.intervals}  ({settings.intervals} 回目の作業後に長い休憩)'
    
    # 残り時間表示を追加
    if session.timer and session.timer.remaining > 0:
        settings_str += f'\n\n現在: **{session.state}**\n残り時間: **{session.timer.time_remaining_to_str(hi_rez=True)}**'
    
    embed = Embed(title='作業セッション設定', description=settings_str, colour=Colour.orange())

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
                return Embed(title=cmd_info[0], description=cmd_info[1], colour=Colour.blue())
        return Embed(title='Error', description='No help found for that command.', colour=Colour.red())


def stats_msg(stats: Stats):
    pomo_str = 'サイクル'
    minutes_str = '分'
    hours_str: str
    time_completed_str: str
    if stats.minutes_completed >= 60:
        hours_str = '時間'
        hours_completed = int(stats.minutes_completed/60)
        time_completed_str = f'{hours_completed}{hours_str}'
        minutes_completed = int(stats.minutes_completed % 60)
        if minutes_completed > 0:
            time_completed_str += f' {minutes_completed}{minutes_str}'
    else:
        if stats.minutes_completed == 1:
            minutes_str = 'minute'
        time_completed_str = f'{stats.minutes_completed}{minutes_str}'
    if stats.pomos_completed == 1:
        pomo_str = 'pomodoro'
    return f'{stats.pomos_completed}{pomo_str}({time_completed_str})'
