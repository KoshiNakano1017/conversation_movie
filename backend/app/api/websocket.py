import asyncio
import json
import time
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from loguru import logger
from sqlalchemy.orm import Session

from app.config import settings
from app.core.database import get_db
from app.core.security import extract_user_id_from_token
from app.deps import DEV_USER_ID
from app.models.job import Job
from app.models.video import Video
from app.models.youtube_publication import YouTubePublication
from app.services.notification_service import (
    build_job_event,
    connection_manager,
    subscribe_job_channel,
)

router = APIRouter(tags=["websocket"])


def _run_db_query(websocket: WebSocket, query_func):
    provider = websocket.app.dependency_overrides.get(get_db, get_db)
    generator = provider()
    db: Session = next(generator)
    try:
        return query_func(db)
    finally:
        try:
            next(generator)
        except StopIteration:
            pass


def _resolve_user_id(websocket: WebSocket) -> str:
    token = websocket.query_params.get("token")
    if token:
        return extract_user_id_from_token(token)
    if settings.APP_DEBUG:
        return DEV_USER_ID
    raise ValueError("認証トークンが必要です")


def _load_job_event(websocket: WebSocket, job_id: str, user_id: str) -> dict[str, Any] | None:
    def _query(db: Session):
        job = db.query(Job).filter(Job.id == job_id, Job.user_id == user_id).first()
        if not job:
            return None

        youtube_url = (
            db.query(YouTubePublication.youtube_url)
            .join(Video, YouTubePublication.video_id == Video.id)
            .filter(Video.job_id == job_id)
            .order_by(YouTubePublication.created_at.desc())
            .scalar()
        )

        return build_job_event(
            job_id=job.id,
            status=job.status,
            progress=job.progress,
            error_message=job.error_message,
            youtube_url=youtube_url,
        )

    return _run_db_query(websocket, _query)


@router.websocket("/ws/jobs/{job_id}")
async def job_progress_websocket(websocket: WebSocket, job_id: str) -> None:
    """
    ジョブ進捗のリアルタイム通知エンドポイント。
    Redis Pub/Sub を優先し、失敗時はDBポーリングでフォールバックする。
    """
    try:
        user_id = _resolve_user_id(websocket)
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    initial_event = _load_job_event(websocket, job_id=job_id, user_id=user_id)
    if initial_event is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await connection_manager.connect(job_id, websocket)
    logger.info("WebSocket接続", job_id=job_id)

    pubsub = subscribe_job_channel(job_id)
    last_payload = json.dumps(initial_event, sort_keys=True, ensure_ascii=False)
    await connection_manager.send_to(websocket, initial_event)

    if initial_event["event"] in {"job_completed", "job_failed"}:
        connection_manager.disconnect(job_id, websocket)
        await websocket.close()
        return

    last_poll_at = 0.0
    try:
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=0.5)
            except asyncio.TimeoutError:
                pass

            if pubsub is not None:
                message = await asyncio.to_thread(pubsub.get_message, True, 0.01)
                if message and message.get("type") == "message":
                    payload = json.loads(message.get("data", "{}"))
                    if payload:
                        serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
                        if serialized != last_payload:
                            last_payload = serialized
                            await connection_manager.send_to(websocket, payload)
                            if payload.get("event") in {"job_completed", "job_failed"}:
                                break

            now = time.monotonic()
            if now - last_poll_at < 2.0:
                continue
            last_poll_at = now

            polled_event = _load_job_event(websocket, job_id=job_id, user_id=user_id)
            if polled_event is None:
                break

            serialized = json.dumps(polled_event, sort_keys=True, ensure_ascii=False)
            if serialized != last_payload:
                last_payload = serialized
                await connection_manager.send_to(websocket, polled_event)
                if polled_event["event"] in {"job_completed", "job_failed"}:
                    break

    except WebSocketDisconnect:
        logger.info("WebSocket切断", job_id=job_id)
    finally:
        if pubsub is not None:
            try:
                pubsub.unsubscribe()
                pubsub.close()
            except Exception:
                pass
        connection_manager.disconnect(job_id, websocket)
