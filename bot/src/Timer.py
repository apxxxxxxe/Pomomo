import time as t

from configs import bot_enum


class Timer:

    def __init__(self, parent):
        duration = parent.settings.duration * 60
        self.parent = parent
        self.running = False
        self.remaining = duration
        self.end = None  # タイマー開始まで設定しない

    def set_time_remaining(self):
        session = self.parent
        if session.state == bot_enum.State.SHORT_BREAK:
            delay = session.settings.short_break * 60
        elif self.parent.state == bot_enum.State.LONG_BREAK:
            delay = session.settings.long_break * 60
        elif session.state == bot_enum.State.CLASSWORK:
            delay = session.settings.duration * 60  # classworkの作業時間
        elif session.state == bot_enum.State.CLASSWORK_BREAK:
            delay = session.settings.short_break * 60  # classworkの休憩時間
        else:
            delay = session.settings.duration * 60
        self.remaining = delay
        # タイマーが実行中の場合のみendを設定
        if self.running:
            self.end = t.time() + delay

    def time_remaining_to_str(self, singular=False, hi_rez=False) -> str:
        if self.running and self.end is not None:
            time_remaining = self.end - t.time()
        else:
            time_remaining = self.remaining

        if time_remaining >= 3600:
            hours_str = str(int(time_remaining/3600)) + '時間'
            time_remaining_str = hours_str
            if hi_rez:
                minutes_str = str(int(time_remaining % 3600 / 60)) + '分'
                time_remaining_str += minutes_str
            return time_remaining_str

        elif time_remaining >= 60:
            total_seconds = round(time_remaining)
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            
            minutes_str = str(minutes) + '分'
            time_remaining_str = minutes_str
            if hi_rez and seconds > 0:
                seconds_str = str(seconds) + '秒'
                time_remaining_str += seconds_str
            return time_remaining_str

        else:
            seconds_str = str(round(time_remaining)) + '秒'
            time_remaining_str = seconds_str
        return time_remaining_str
