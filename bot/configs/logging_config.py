import logging
import logging.handlers
import os
from pathlib import Path

def setup_logging():
    """
    loggingモジュールの設定を行う
    ログレベルは環境変数LOG_LEVELで制御可能（デフォルト: INFO）
    """
    # ログディレクトリの作成
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # ログレベルの取得（環境変数またはデフォルト）
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    numeric_level = getattr(logging, log_level, logging.INFO)
    
    # ルートロガーの設定
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # 既存のハンドラをクリア（重複防止）
    root_logger.handlers.clear()
    
    # フォーマッターの定義
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # コンソールハンドラの設定
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # ファイルハンドラの設定（ローテーション付き）
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_dir / "pomomo.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=30,  # 30ファイルまで保持
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)  # ファイルには常にDEBUGレベル以上を記録
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # エラー専用ファイルハンドラ
    error_file_handler = logging.handlers.RotatingFileHandler(
        filename=log_dir / "pomomo_error.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=30,  # 30ファイルまで保持
        encoding='utf-8'
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(formatter)
    root_logger.addHandler(error_file_handler)
    
    # discord.pyのログレベル調整（デバッグ時以外はWARNINGに）
    if numeric_level != logging.DEBUG:
        logging.getLogger('discord').setLevel(logging.WARNING)
        logging.getLogger('discord.http').setLevel(logging.WARNING)
        logging.getLogger('discord.gateway').setLevel(logging.WARNING)
    
    return root_logger

def get_logger(name: str) -> logging.Logger:
    """
    モジュール用のロガーを取得
    
    Args:
        name: モジュール名（通常は__name__を渡す）
    
    Returns:
        logging.Logger: 設定済みのロガー
    """
    return logging.getLogger(name)