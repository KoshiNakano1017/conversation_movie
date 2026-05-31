from fastapi import APIRouter

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/google")
async def google_auth() -> dict:
    """Google OAuthトークン交換（実装予定 - TASK-004）"""
    return {"message": "TODO: TASK-004で実装"}


@router.post("/refresh")
async def refresh_token() -> dict:
    """トークンリフレッシュ（実装予定 - TASK-004）"""
    return {"message": "TODO: TASK-004で実装"}


@router.post("/logout")
async def logout() -> dict:
    """ログアウト（実装予定 - TASK-004）"""
    return {"message": "TODO: TASK-004で実装"}
