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

STILL_THERE = ['そうですね！ちょっと確認でした😊',
               'クールです！']

# ユーザー操作エラー（詳細説明）
VOICE_CHANNEL_REQUIRED_ERR = "おっと！まずボイスチャンネルに参加してくださいね 🎧"
BOT_CONNECT_PERMISSION_ERR = "ボットに「{channel_name}」への参加権限がありません…\nチャンネルの権限設定をご確認ください"
BOT_SPEAK_PERMISSION_ERR = "ボットに「{channel_name}」での発言権限がありません…\nチャンネルの権限設定をご確認ください"
SAME_VOICE_CHANNEL_REQUIRED_ERR = "`{command}`コマンドは「{bot_name}」と同じボイスチャンネル「{channel_name}」に参加してから実行してくださいね 😊"

# パラメータエラー
INVALID_DURATION_ERR = "時間は1〜{max_minutes}分で設定してくださいね！😊\n例: `/pomodoro 25 5`"
COUNTDOWN_SKIP_NOT_ALLOWED = "カウントダウンはスキップできません 💭 終了するには`/stop`をどうぞ"
INVALID_PARAMETER_ERR = "無効なパラメータです… 正しい値を入力してくださいね"

# セッション状態エラー
NO_SESSION_TO_STOP = "停止するセッションがありません 😊"
NO_SESSION_TO_SKIP = "スキップするセッションがありません 😊"
ACTIVE_SESSION_IN_CHANNEL = "「{channel_name}」でセッション実行中です 💭\nまずVCに参加後`/stop`で停止してくださいね"

# 同時実行エラー
COMMAND_ALREADY_RUNNING = "すでに`{command}`が実行されています🫡"
VOICE_OPERATION_IN_PROGRESS = "音声チャンネルの操作を処理中です🫡 少しお待ちください"

# システムエラー（簡潔）
POMODORO_START_FAILED = "`/pomodoro`の開始に失敗しました 💭"
START_SESSION_FAILED = "`/start`の開始に失敗しました 💭"
COUNTDOWN_START_FAILED = "`/countdown`の開始に失敗しました 💭"
SESSION_STOP_FAILED = "`/stop`処理中にエラーが発生しました 💭"
AUTOMUTE_ENABLE_FAILED = "`/enableautomute`に失敗しました 💭"
AUTOMUTE_DISABLE_FAILED = "`/disableautomute`に失敗しました 💭"
HELP_COMMAND_ERROR = "有効なコマンドを入力してくださいね！😊\n`/help`で一覧を確認できます"

# automute関連エラー
AUTOMUTE_REQUIRES_BOT_IN_VC = "automuteを使用するには、まずPomomoが音声チャンネルにいる必要があります 🎧"
AUTOMUTE_ALREADY_ENABLED = "「{channel_name}」のautomuteは既にオンです 😊"
AUTOMUTE_ALREADY_DISABLED = "「{channel_name}」のautomuteは既にオフです 😊"
