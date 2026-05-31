from jose import JWTError, jwt
from loguru import logger

from app.config import settings
from app.core.exceptions import AuthenticationError

ALGORITHM = "HS256"


def verify_supabase_jwt(token: str) -> dict:
    """
    SupabaseのJWTトークンを検証してペイロードを返す。

    Supabaseのトークンはサービスロールキーの最初の32バイトをsecretとして使用する。
    """
    try:
        secret = settings.SUPABASE_SERVICE_ROLE_KEY

        payload = jwt.decode(
            token,
            secret,
            algorithms=[ALGORITHM],
            options={"verify_aud": False},
        )
        return payload

    except JWTError as error:
        logger.warning("JWT検証失敗", error=str(error))
        raise AuthenticationError(
            code="AUTH001",
            message="無効なトークンです",
            detail=str(error),
        )


def extract_user_id_from_token(token: str) -> str:
    """JWTトークンからユーザーIDを抽出する"""
    payload = verify_supabase_jwt(token)
    user_id = payload.get("sub")

    if not user_id:
        raise AuthenticationError(
            code="AUTH002",
            message="トークンにユーザーIDが含まれていません",
        )

    return user_id
