from fastapi import APIRouter

router = APIRouter(prefix="/api/youtube", tags=["youtube"])


@router.get("/auth-url")
async def get_auth_url() -> dict:
    """YouTube OAuth認証URL取得（実装予定 - TASK-013）"""
    return {"auth_url": "TODO"}


@router.post("/publish", status_code=202)
async def publish_to_youtube() -> dict:
    """YouTube投稿（実装予定 - TASK-013）"""
    return {"message": "TODO: TASK-013で実装"}
