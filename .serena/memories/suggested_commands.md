# 推奨コマンド

## 開発環境セットアップ
```bash
# 依存関係のインストール
pip install -r requirements.txt

# 環境変数設定（.envファイルを作成）
# DISCORD_TOKEN=your_bot_token_here
```

## プロジェクト実行
```bash
# ボットの起動
python bot/main.py

# または
cd bot && python main.py
```

## 開発用コマンド
```bash
# Pythonバージョン確認
python --version

# 依存関係確認
pip list

# 依存関係のアップデート
pip install -r requirements.txt --upgrade
```

## システムコマンド（Linux）
```bash
# ファイル一覧
ls -la

# ディレクトリ移動
cd path/to/directory

# ファイル検索
find . -name "*.py" -type f

# パターン検索
grep -r "pattern" .

# プロセス確認
ps aux | grep python
```

## Git操作
```bash
# 状態確認
git status

# 変更をステージング
git add .

# コミット
git commit -m "commit message"

# プッシュ
git push origin main
```

## 注意事項
- このプロジェクトにはlint/format/testの自動化コマンドは設定されていません
- テストフレームワークは使用されていません
- ボット実行にはDISCORD_TOKENの環境変数が必要です