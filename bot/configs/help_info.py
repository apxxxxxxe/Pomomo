from . import config


SUMMARY = 'Pomomoは、あなたと友達が一緒に勉強する際の進捗管理をサポートします！\n' \
          '集中時間を設定して作業し、休憩時間にチャットを楽しみましょう。\n\n' \
          '必須パラメータは<>で、オプションパラメータは[]で囲まれています。\n' \
          f'例えば、\"{config.CMD_PREFIX}start\"でデフォルト値でポモドーロセッションを開始したり、' \
          f'\"{config.CMD_PREFIX}start 30 10\"でポモドーロと短い休憩の時間をカスタマイズできます！\n'

POMO_ARGS = 'pomodoro: 作業の時間（分）（デフォルト: 20分）\n' \
            'short_break: 短い休憩の時間（分）（デフォルト: 5分）\n' \
            'long_break: 長い休憩の時間（分）（デフォルト: 15分）\n' \
            'intervals: 長い休憩までのポモドーロ回数（デフォルト: 4回）'

COUNTDOWN_ARGS = '複数単語のタイトルは" "で囲んでください（デフォルト: "Countdown"）。\n' \
                 '音声チャンネルの音声アラートを無効にするには"mute"パラメータを追加してください。\n\n' \
                 f'使用例: {config.CMD_PREFIX}countdown 5 "宿題を終わらせる!" mute'

COMMANDS = {
    'コントロールコマンド': {
        'start': ['/start [pomodoro] [short_break] [long_break] [intervals]',
            'オプションのカスタム設定でポモドーロセッションを開始します。\n\n' + POMO_ARGS],
        'skip': ['/skip', '現在のインターバルをスキップして次のポモドーロまたは休憩を開始'],
        'stop': ['/stop', 'セッションを終了'],
        'countdown': ['/countdown <duration> [title] [mute]',
            'リアルタイムで更新されるタイマー付きのピン留めメッセージを送信するカウントダウンを開始します。\n\n' +
            COUNTDOWN_ARGS]
    },
    'サブスクリプションコマンド': {
        'enableautomute': ['/enableautomute', 'ポモドーロインターバル中に\n自動的にスピーカーとマイクをオフにする機能を有効にします。'],
        'disableautomute': ['/disableautomute', 'ポモドーロインターバル中に\n自動的にスピーカーとマイクをオフにする機能を無効にします。']
    }
}
