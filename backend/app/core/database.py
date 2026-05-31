from collections.abc import Generator

from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

SQLITE_FALLBACK_URL = "sqlite:///./dev.db"


class Base(DeclarativeBase):
    """全モデルの共通ベースクラス"""
    pass


def create_db_engine():
    """
    データベースエンジンを作成する。
    DATABASE_URL が未設定の場合はSQLiteにフォールバックして起動を継続する。
    """
    database_url = settings.DATABASE_URL

    if not database_url:
        logger.warning(
            "DATABASE_URL が未設定です。SQLiteで起動します（開発用）"
        )
        database_url = SQLITE_FALLBACK_URL

    # asyncpg形式をpsycopg2形式に変換（同期処理用）
    if database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")

    is_sqlite = database_url.startswith("sqlite")

    connect_args = {"check_same_thread": False} if is_sqlite else {}
    pool_kwargs = {} if is_sqlite else {"pool_size": 5, "max_overflow": 10}

    return create_engine(
        database_url,
        connect_args=connect_args,
        pool_pre_ping=not is_sqlite,
        echo=settings.APP_DEBUG,
        **pool_kwargs,
    )


engine = create_db_engine()

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPIの依存性注入用のDBセッション取得関数"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> bool:
    """DB接続の死活確認"""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception as error:
        logger.error("DB接続エラー", error=str(error))
        return False
