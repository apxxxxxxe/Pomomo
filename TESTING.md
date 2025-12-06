# Pomomoテスト実行ガイド

このドキュメントでは、PomodoroボットのDiscordコマンドをpytestで自動テストする方法について説明します。

## テスト環境のセットアップ

### 1. テスト用依存関係のインストール

```bash
pip install -r requirements-dev.txt
```

### 2. テストの実行

#### 基本実行
```bash
# 環境変数を設定してテストを実行
TESTING=1 PYTHONPATH=/path/to/Pomomo/bot pytest tests/ -v
```

#### 簡単な実行方法（推奨）
```bash
# テストランナースクリプトを使用
python test_runner.py
```

#### 特定のテストファイルのみ実行
```bash
TESTING=1 PYTHONPATH=bot pytest tests/unit/test_basic.py -v
```

#### カバレッジ付きテスト実行
```bash
TESTING=1 PYTHONPATH=bot pytest tests/ --cov=bot --cov-report=html -v
```

## テスト構造

### ディレクトリ構成
```
tests/
├── __init__.py
├── conftest.py              # pytest設定とフィクスチャ
├── mocks/
│   ├── __init__.py
│   ├── discord_mocks.py     # Discordオブジェクトのモック
│   └── voice_mocks.py       # 音声クライアントのモック
├── unit/
│   ├── test_basic.py        # 基本的なセットアップテスト
│   ├── test_control_cog.py  # Controlコグのテスト
│   ├── test_info_cog.py     # Infoコグのテスト
│   ├── test_subscribe_cog.py # Subscribeコグのテスト
│   └── test_session_logic.py # セッション管理のテスト
└── integration/
    └── test_bot_integration.py # 統合テスト（未実装）
```

### テストの種類

1. **基本セットアップテスト** (`test_basic.py`)
   - モックオブジェクトの動作確認
   - 基本的なインポートとフィクスチャテスト

2. **Controlコグテスト** (`test_control_cog.py`)
   - `/pomodoro` コマンドのテスト
   - `/stop` コマンドのテスト
   - `/skip` コマンドのテスト
   - `/countdown` コマンドのテスト
   - `/classwork` コマンドのテスト
   - バリデーションロジックのテスト

3. **Infoコグテスト** (`test_info_cog.py`)
   - `/help` コマンドのテスト
   - エラーハンドリングのテスト

4. **Subscribeコグテスト** (`test_subscribe_cog.py`)
   - `/enableautomute` コマンドのテスト
   - `/disableautomute` コマンドのテスト
   - 音声状態変更イベントのテスト

5. **セッション管理テスト** (`test_session_logic.py`)
   - セッションの作成・削除
   - セッション設定の検証
   - タイマー機能のテスト
   - 統計情報のテスト

## モック機能

### Discordオブジェクトのモック
- `MockBot`: Discordボットのモック
- `MockInteraction`: スラッシュコマンドインタラクションのモック
- `MockUser`: Discordユーザーのモック
- `MockGuild`: Discordサーバーのモック
- `MockVoiceChannel`: 音声チャンネルのモック
- `MockTextChannel`: テキストチャンネルのモック

### 音声機能のモック
- `MockVoiceClient`: 音声クライアントのモック
- `MockAudioSource`: 音声ソースのモック
- `MockVoiceManager`: 音声管理のモック

## テスト実行時の注意点

1. **環境変数の設定**
   - `TESTING=1` を設定することで、テストモードを有効化
   - `PYTHONPATH` にbotディレクトリを追加してインポートを可能にする

2. **Discord API の分離**
   - 実際のDiscord APIは呼び出されません
   - すべてのDiscord機能はモックで代替されています
   - ネットワーク接続は不要です

3. **非同期テストのサポート**
   - `@pytest.mark.asyncio` デコレータを使用
   - 非同期関数のテストが可能

## テスト例

### 基本的なコマンドテスト
```python
@pytest.mark.asyncio
async def test_pomodoro_command(control_cog, mock_interaction):
    with patch('cogs.control.Settings') as mock_settings:
        mock_settings.is_valid_interaction.return_value = True
        
        await control_cog.pomodoro(mock_interaction, pomodoro=25)
        
        mock_interaction.response.defer.assert_called_once()
```

### エラーハンドリングテスト
```python
@pytest.mark.asyncio
async def test_command_error_handling(cog, mock_interaction):
    with patch('module.function', side_effect=Exception("Test error")):
        await cog.command(mock_interaction)
        
        # エラーレスポンスの確認
        mock_interaction.response.send_message.assert_called_with(
            "エラーメッセージ", ephemeral=True
        )
```

## CI/CD での実行

### GitHub Actions設定例
```yaml
- name: Run tests
  run: |
    pip install -r requirements-dev.txt
    TESTING=1 PYTHONPATH=bot pytest tests/ -v --cov=bot
```

### ローカル開発での継続的テスト
```bash
# pytest-watchを使用した自動テスト実行
pip install pytest-watch
TESTING=1 PYTHONPATH=bot ptw tests/ -- -v
```

## トラブルシューティング

### よくある問題

1. **インポートエラー**
   - `PYTHONPATH=bot` が正しく設定されているか確認
   - botディレクトリ内の相対インポートが正しいか確認

2. **非同期テストの問題**
   - `@pytest.mark.asyncio` デコレータを追加
   - `pytest-asyncio` がインストールされているか確認

3. **モックが動作しない**
   - パッチのパスが正しいか確認
   - モックオブジェクトの設定が適切か確認

### デバッグ方法
```bash
# より詳細な出力でテスト実行
TESTING=1 PYTHONPATH=bot pytest tests/ -vs --tb=long

# 特定のテストのみ実行
TESTING=1 PYTHONPATH=bot pytest tests/unit/test_basic.py::TestBasicSetup::test_mock_objects_work -v

# pdbデバッガーを使用
TESTING=1 PYTHONPATH=bot pytest tests/ --pdb
```

## テストの拡張

新しいコマンドやフィーチャーのテストを追加する際は：

1. 適切なテストファイルに新しいテストメソッドを追加
2. 必要に応じて新しいモックオブジェクトを作成
3. テストケースに適切なアノテーションを追加（`@pytest.mark.asyncio`等）
4. エラーケースと正常ケースの両方をテスト