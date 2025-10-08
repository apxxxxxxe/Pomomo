# Pomomo Discord Bot - Project Overview

## プロジェクトの目的
PomomoはPomodoro技術を使用したDiscordボットです。生産性と社交のバランスを取り、作業と休憩の間隔を交互に取ることで生産性を最大化し、燃え尽き症候群を最小化します。

## 主な機能
- Pomodoro/休憩間隔の音声アラート再生
- リアルタイム更新カウントダウンタイマー
- Pomodoro間隔中の自動ミュート/ディーフェン
- 早期リマインダーアラート
- セッションロック機能
- DM通知サブスクリプション

## 技術スタック
- **言語**: Python 3.11+
- **主要ライブラリ**: 
  - discord.py 1.6.0 (Discord API)
  - aiohttp 3.7.4.post0 (非同期HTTP)
  - PyNaCl 1.4.0 (音声処理)
  - python-dotenv 0.15.0 (環境変数)
  - PyYAML 5.4.1 (設定ファイル)

## コードベース構造
```
bot/
├── main.py                 # メインエントリーポイント
├── configs/                # 設定ファイル
│   ├── config.py          # メイン設定
│   ├── bot_enum.py        # 列挙型定義
│   ├── help_info.py       # ヘルプ情報
│   └── user_messages.py   # ユーザーメッセージ
├── cogs/                  # Discordコマンドモジュール
│   ├── control.py         # メイン制御コマンド
│   ├── info.py           # 情報コマンド
│   └── subscribe.py      # サブスクリプションコマンド
└── src/                  # コアロジック
    ├── session/          # セッション管理
    ├── subscriptions/    # サブスクリプション機能
    ├── voice_client/     # 音声クライアント管理
    ├── utils/           # ユーティリティ
    ├── Settings.py      # 設定クラス
    ├── Stats.py         # 統計クラス
    └── Timer.py         # タイマークラス
```