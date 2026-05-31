from celery import Task
from loguru import logger

from app.celery_app import celery_app


@celery_app.task(
    name="workers.youtube_upload",
    queue="upload",
    bind=True,
    max_retries=5,
    default_retry_delay=120,
)
def run_youtube_upload_task(self: Task, job_id: str, video_id: str) -> dict:
    """
    YouTube Data APIを使って動画を投稿するタスク。
    実装予定: TASK-013
    """
    logger.info("YouTube投稿タスク開始", job_id=job_id, video_id=video_id)
    return {"job_id": job_id, "status": "youtube_todo"}
