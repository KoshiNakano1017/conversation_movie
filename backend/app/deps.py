from collections.abc import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import AuthenticationError
from app.core.security import extract_user_id_from_token

http_bearer = HTTPBearer(auto_error=False)


DEV_USER_ID = "00000000-0000-0000-0000-000000000001"


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
) -> str:
    """
    リクエストのAuthorizationヘッダーからユーザーIDを取得する。
    トークンがない・無効な場合は401エラーを返す。

    開発環境（APP_DEBUG=True）ではトークンなしでも固定のdevユーザーIDを返す。
    本番環境では必ずJWTが必要。
    """
    from app.config import settings

    if not credentials:
        if settings.APP_DEBUG:
            logger.debug("開発モード: 認証トークンなし、devユーザーとして処理")
            return DEV_USER_ID
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="認証トークンが必要です",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = extract_user_id_from_token(credentials.credentials)
        return user_id
    except AuthenticationError as error:
        if settings.APP_DEBUG:
            logger.debug("開発モード: トークン検証失敗、devユーザーとして処理")
            return DEV_USER_ID
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error.message,
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_optional_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
) -> str | None:
    """
    トークンがある場合はユーザーIDを返し、ない場合はNoneを返す。
    認証が任意のエンドポイントで使用する。
    """
    if not credentials:
        return None

    try:
        return extract_user_id_from_token(credentials.credentials)
    except AuthenticationError:
        return None


def get_db_session() -> Generator[Session, None, None]:
    """DBセッションの依存性注入エイリアス"""
    yield from get_db()
