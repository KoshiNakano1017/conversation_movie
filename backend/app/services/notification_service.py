"""
WebSocket通知の補助サービス。

- WebSocket接続のインメモリ管理
- Redis Pub/Sub 経由のジョブ通知配信
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

import redis
from fastapi import WebSocket
from loguru import logger

from app.config import settings
from app.models.job import JobStatus

JOB_CHANNEL_PREFIX = "job_events"


class ConnectionManager:
    """ジョブ単位のWebSocket接続を管理する。"""

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, job_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[job_id].add(websocket)

    def disconnect(self, job_id: str, websocket: WebSocket) -> None:
        sockets = self._connections.get(job_id)
        if not sockets:
            return
        sockets.discard(websocket)
        if not sockets:
            self._connections.pop(job_id, None)

    async def send_to(self, websocket: WebSocket, payload: dict[str, Any]) -> None:
        await websocket.send_json(payload)

    async def broadcast(self, job_id: str, payload: dict[str, Any]) -> None:
        for websocket in list(self._connections.get(job_id, set())):
            try:
                await websocket.send_json(payload)
            except Exception:
                self.disconnect(job_id, websocket)


connection_manager = ConnectionManager()


def get_job_channel(job_id: str) -> str:
    return f"{JOB_CHANNEL_PREFIX}:{job_id}"


def _status_to_step(job_status: JobStatus) -> tuple[str, str]:
    """
    ジョブステータスをUIのステップ名と状態へ変換する。

    Returns:
        (step_name, step_status)
        step_status は pending / in_progress / completed / failed
    """
    if job_status in {JobStatus.FAILED, JobStatus.CANCELLED}:
        return "analyzing", "failed"
    if job_status in {JobStatus.PENDING, JobStatus.UPLOADING, JobStatus.TRANSCRIBING, JobStatus.DIARIZING}:
        return "analyzing", "pending"
    if job_status in {JobStatus.ANALYZING, JobStatus.GENERATING_SUBTITLES}:
        return "analyzing", "in_progress"
    if job_status == JobStatus.GENERATING_VIDEO:
        return "generating_video", "in_progress"
    if job_status in {JobStatus.GENERATING_SHORTS, JobStatus.UPLOADING_YOUTUBE}:
        return "uploading_youtube", "in_progress"
    if job_status == JobStatus.COMPLETED:
        return "uploading_youtube", "completed"
    return "analyzing", "pending"


def build_job_event(
    *,
    job_id: str,
    status: JobStatus,
    progress: int,
    error_message: str | None = None,
    youtube_url: str | None = None,
) -> dict[str, Any]:
    step, step_status = _status_to_step(status)
    base_data: dict[str, Any] = {
        "job_id": job_id,
        "progress": progress,
        "current_status": status.value,
        "step": step,
        "status": step_status,
    }

    if status == JobStatus.COMPLETED:
        if youtube_url:
            base_data["youtube_url"] = youtube_url
        return {"event": "job_completed", "data": base_data}

    if status in {JobStatus.FAILED, JobStatus.CANCELLED}:
        if error_message:
            base_data["message"] = error_message
        return {"event": "job_failed", "data": base_data}

    return {"event": "job_progress", "data": base_data}


def _create_redis_client() -> redis.Redis | None:
    try:
        return redis.from_url(settings.REDIS_URL, decode_responses=True)
    except Exception as error:
        logger.warning("Redisクライアント作成失敗（通知はポーリングにフォールバック）", error=str(error))
        return None


def publish_job_event(payload: dict[str, Any]) -> None:
    job_id = payload.get("data", {}).get("job_id")
    if not job_id:
        return
    redis_client = _create_redis_client()
    if redis_client is None:
        return

    try:
        redis_client.publish(get_job_channel(job_id), json.dumps(payload, ensure_ascii=False))
    except Exception as error:
        logger.debug("Redis publish失敗（通知はポーリングで継続）", error=str(error))


def subscribe_job_channel(job_id: str) -> redis.client.PubSub | None:
    redis_client = _create_redis_client()
    if redis_client is None:
        return None

    try:
        pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
        pubsub.subscribe(get_job_channel(job_id))
        return pubsub
    except Exception as error:
        logger.debug("Redis subscribe失敗（通知はポーリングで継続）", error=str(error))
        return None
