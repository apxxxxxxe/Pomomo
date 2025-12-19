# CLAUDE.md

**ユーザーへの応答は日本語で行うこと**

このファイルは、このリポジトリのコードを操作する際にClaude Code (claude.ai/code) にガイダンスを提供します。

## プロジェクト概要

Pomomoは、Discord上でPomodoro技術を実装するボットです。作業と休憩の間隔を管理し、生産性向上を支援します。Python 3.11とdiscord.py 1.6.0を使用して構築されています。

## 開発コマンド

### 環境セットアップ
```bash
# 仮想環境作成
python -m venv venv

# 依存関係インストール
pip install -r requirements.txt

# 環境変数設定（.envファイルに以下を設定）
DISCORD_TOKEN=your_discord_bot_token
```

### ボット実行
```bash
# メイン実行方法
cd bot && python main.py
```

### 開発時の確認コマンド
```bash
# Python環境確認
python --version

# 依存関係一覧
pip list

# 構文チェック
python -m pylint bot/main.py
```

### テスト実行
```bash
# 全テストを実行（テスト環境変数付き）
TESTING=1 PYTHONPATH=/home/applepie/ghq/github.com/apxxxxxxe/Pomomo/bot pytest tests/ -v

# ユニットテストのみ
TESTING=1 PYTHONPATH=/home/applepie/ghq/github.com/apxxxxxxe/Pomomo/bot pytest tests/unit/ -v

# 特定のテストファイル実行
TESTING=1 PYTHONPATH=/home/applepie/ghq/github.com/apxxxxxxe/Pomomo/bot pytest tests/unit/test_basic.py -v

# 特定のテストメソッド実行
TESTING=1 PYTHONPATH=/home/applepie/ghq/github.com/apxxxxxxe/Pomomo/bot pytest tests/unit/test_control_cog.py::TestControl::test_pomodoro_command_valid_parameters -v
```

## アーキテクチャ

### コア構造
- **bot/main.py**: エントリーポイント、Cogsの読み込み
- **bot/configs/**: 設定ファイル群（config.py、bot_enum.py等）
- **bot/cogs/**: Discord.pyのCogsパターンによるコマンド実装
  - control.py: メイン制御コマンド（start、pause、resume等）
  - info.py: 情報取得コマンド（status、stats等）
  - subscribe.py: サブスクリプション機能
- **bot/src/**: コアビジネスロジック
  - session/: セッション管理（Session.py、session_manager.py等）
  - subscriptions/: DM通知、自動ミュート機能
  - voice_client/: Discord音声クライアント管理
  - utils/: メッセージ構築、音声再生ユーティリティ

### 重要なクラス
- **Session**: Pomodoroセッション状態管理
- **Timer**: タイマー機能実装
- **Settings**: セッション設定管理
- **Stats**: セッション統計情報

## コーディング規約

### 命名規則
- クラス: PascalCase (例: Session, Timer)
- 関数/変数: snake_case (例: active_sessions, kill_if_idle)
- 定数: UPPER_SNAKE_CASE (例: CMD_PREFIX, TIMEOUT_SECONDS)

### プロジェクト固有の重要点
- セッション管理は`session_manager.py`で中央管理
- 音声機能はPyNaClライブラリを使用
- 非同期処理（async/await）の適切な使用が必須
- Discord Intentsの明示的設定が必要
- コマンドプレフィックスは設定ファイルで管理（現在は'test!'）

### ファイル編集時の注意
- 既存のdiscord.pyパターン（Cogs）に従う
- セッション状態の整合性を保つ
- 音声処理部分は慎重に変更する
- 環境変数の取り扱いに注意（.envファイル使用）

## 完了時チェックリスト

1. **構文エラーの確認**: `python -m py_compile`で主要ファイルをチェック
2. **テスト実行**: `TESTING=1 PYTHONPATH=/home/applepie/ghq/github.com/apxxxxxxe/Pomomo/bot pytest tests/ -v`でテストを実行し、全て成功することを確認
3. **ボット起動確認**: `python bot/main.py`で正常起動を確認
4. **基本機能確認**: Discordでボットがオンラインになることを確認
5. **環境変数確認**: DISCORD_TOKENが正しく設定されていることを確認
6. **依存関係確認**: requirements.txtに新しい依存関係があれば追加

## テスト方針

### テスト構造
- **tests/unit/**: ユニットテスト（個別コンポーネントのテスト）
- **tests/integration/**: 統合テスト（複数コンポーネント間の連携テスト）
- **tests/mocks/**: Discordオブジェクト用のモッククラス
  - discord_mocks.py: Discord API関連のモック（Bot, User, Guild, Channelなど）
  - voice_mocks.py: 音声機能関連のモック（VoiceClient, AudioSourceなど）
- **tests/conftest.py**: pytestの設定とフィクスチャ定義

### テスト方針の特徴
1. **Discord APIをモック化**: 実際のDiscord APIを呼び出さずにテスト実行
2. **非同期処理のサポート**: async/awaitを使ったコードのテストに対応
3. **環境分離**: `TESTING=1`環境変数でテスト環境を識別
4. **フィクスチャベース**: pytest fixtureを活用した再利用可能なテストセットアップ
5. **モジュール独立性**: 各Cogや機能ごとに独立したテストファイル

### テスト実装時の注意点
- Discord関連のオブジェクトは必ずmocksディレクトリのモッククラスを使用
- 非同期メソッドには`@pytest.mark.asyncio`デコレータを付与
- `PYTHONPATH`にbotディレクトリを追加してモジュールインポートを可能にする
- 実際のDiscord API呼び出しやファイルI/Oは避ける

注意: このプロジェクトには自動lint、formatツールは設定されていませんが、pytestベースの自動テストは実装されています。
