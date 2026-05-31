import sys
from pathlib import Path

from loguru import logger

from app.config import settings


def setup_logging() -> None:
    """アプリケーション全体のログ設定を初期化する"""
    logger.remove()

    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    if settings.APP_DEBUG:
        logger.add(sys.stdout, format=log_format, level="DEBUG", colorize=True)
    else:
        logger.add(sys.stdout, format=log_format, level="INFO", colorize=False, serialize=True)

    # ログディレクトリを自動作成してファイルログを追加
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    logger.add(
        str(log_dir / "app_{time:YYYY-MM-DD}.log"),
        format=log_format,
        level="INFO",
        rotation="1 day",
        retention="30 days",
        compression="gz",
    )
