class State:
    # 内部定数（一意性を保証）
    POMODORO = 'POMODORO'
    SHORT_BREAK = 'SHORT_BREAK'
    LONG_BREAK = 'LONG_BREAK'
    COUNTDOWN = 'COUNTDOWN'
    CLASSWORK = 'CLASSWORK'
    CLASSWORK_BREAK = 'CLASSWORK_BREAK'
    
    # 表示用文字列マッピング
    DISPLAY_NAMES = {
        'POMODORO': '作業中',
        'SHORT_BREAK': '短い休憩',
        'LONG_BREAK': '長い休憩',
        'COUNTDOWN': 'カウントダウン',
        'CLASSWORK': '作業中',
        'CLASSWORK_BREAK': '休憩中'
    }
    
    # 作業状態（ミュート対象）
    WORK_STATES = [COUNTDOWN, POMODORO, CLASSWORK]
    # 休憩状態（アンミュート対象）
    BREAK_STATES = [SHORT_BREAK, LONG_BREAK, CLASSWORK_BREAK]
    
    @classmethod
    def get_display_name(cls, state):
        return cls.DISPLAY_NAMES.get(state, state)


class AlertPath:
    POMO_START = 'sounds/pomo_start.mp3'
    POMO_END = 'sounds/pomo_end.mp3'
    LONG_BREAK_START = 'sounds/long_break.mp3'


