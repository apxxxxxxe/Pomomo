# コード規約とスタイル

## コーディングスタイル
- **言語**: Python 3.11+
- **インデント**: スペース4つ
- **命名規則**: 
  - クラス: PascalCase (例: Session, Timer)
  - 関数/変数: snake_case (例: active_sessions, kill_if_idle)
  - 定数: UPPER_SNAKE_CASE (例: CMD_PREFIX, TIMEOUT_SECONDS)

## プロジェクト固有の規約
- **設定管理**: `bot/configs/config.py`で中央管理
- **コマンドプレフィックス**: 'test!' (開発用設定)
- **モジュール構造**: discord.pyのCogsパターンを使用
- **セッション管理**: セッションマネージャーによる中央管理
- **エラーハンドリング**: 各セッションで独立したタイムアウト処理

## ファイル組織
- **エントリーポイント**: `bot/main.py`
- **設定ファイル**: `bot/configs/`
- **コマンド実装**: `bot/cogs/`
- **コアロジック**: `bot/src/`
- **音響ファイル**: `sounds/`

## Discord.py特有の規約
- Cogsを使用したコマンド分離
- 非同期処理の適切な使用（async/await）
- Intentsの明示的な設定
- セッション状態の適切な管理

## 依存関係管理
- `requirements.txt`で明示的にバージョン指定
- 古いバージョンのライブラリを使用（discord.py 1.6.0など）
- 環境変数は`python-dotenv`で管理