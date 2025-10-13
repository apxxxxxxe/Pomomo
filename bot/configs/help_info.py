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

COMMANDS = {'コントロールコマンド': {'start': ['start [pomodoro] [short_break] [long_break] [intervals]',
                                           'オプションのカスタム設定でポモドーロセッションを開始します。\n\n' + POMO_ARGS],
                                 'pause': ['pause', 'セッションを一時停止'],
                                 'resume': ['resume', 'セッションを再開'],
                                 'restart': ['restart', 'タイマーを再開始'],
                                 'skip': ['skip', '現在のインターバルをスキップして次のポモドーロまたは休憩を開始'],
                                 'stop': ['stop', 'セッションを終了'],
                                 'edit': ['edit <pomodoro> [short_break] [long_break] [intervals]',
                                          '新しい設定でセッションを継続\n\n' + POMO_ARGS],
                                 'countdown': ['countdown <duration> [title] [mute]',
                                               'リアルタイムで更新されるタイマー付きのピン留めメッセージを送信するカウントダウンを開始します。\n\n' +
                                               COUNTDOWN_ARGS]
                                 },
            '情報コマンド': {'time': ['time', '残り時間を取得'],
                              'stats': ['stats', 'セッション統計を取得'],
                              'settings': ['settings', 'セッション設定を取得'],
                              'servers': ['servers', 'Pomomoを使用しているサーバー数を確認']},
            'サブスクリプションコマンド': {'dm': ['dm', 'サーバーのセッションのDMアラート購読を切り替え'],
                                      'enableautoshush': ['enableautoshush [all]', 'ポモドーロインターバル中に自動的に'
                                                                          'スピーカーとマイクをオフにする機能を有効にします。\n'
                                                                          'ミュートとスピーカーオフの権限を持つメンバーは'
                                                                          '"all"パラメータを追加してポモドーロ音声チャンネルの'
                                                                          '全員をauto_shush有効にできます。'],
                                     'disableautoshush': ['disableautoshush [all]', 'ポモドーロインターバル中に自動的に'
                                                                           'スピーカーとマイクをオフにする機能を無効にします。\n'
                                                                           'ミュートとスピーカーオフの権限を持つメンバーは'
                                                                           '"all"パラメータを追加してポモドーロ音声チャンネルの'
                                                                           '全員をauto_shush無効にできます。']}}
