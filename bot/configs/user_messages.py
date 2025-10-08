from . import config

NO_ACTIVE_SESSION_ERR = 'アクティブなセッションがありません。\n' \
                        f'コマンド \'{config.CMD_PREFIX}start [pomodoro] [short_break] [long_break] [intervals]\' を使用してください。'

ACTIVE_SESSION_EXISTS_ERR = 'サーバーに既にアクティブなセッションが存在します。\n'

NUM_OUTSIDE_ONE_AND_MAX_INTERVAL_ERR = f'1分から{config.MAX_INTERVAL_MINUTES}分の間で時間を設定してください。'

NUM_OUTSIDE_ONE_AND_SIXTY_ERR = '時間は1分から60分の間で設定してください。'

MISSING_ARG_ERR = '少なくとも1つの数字を入力してください。'

GREETINGS = ['やあやあ！始めましょう！',
             'こんにちは！さあ始めましょう！',
             '生産性の時間です！',
             '作業を始めましょう！']

ENCOURAGEMENTS = ['続けていきましょう！',
                  '良い調子です！',
                  'その調子です！',
                  'できています！',
                  'すばらしいです！']

STILL_THERE = ['ふぅ...心配になってきました😅',
               'そうですね！ちょっと確認でした😊',
               'クールです！']
