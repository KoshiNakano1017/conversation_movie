from celery import Task
from loguru import logger

from app.celery_app import celery_app


@celery_app.task(
    name="workers.diarization",
    queue="ai",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def run_diarization_task(self: Task, job_id: str) -> dict:
    """
    pyannote.audioを使って話者分離するタスク。
    実装予定: TASK-014 (Phase 2)
    """
    logger.info("話者分離タスク開始", job_id=job_id)
    return {"job_id": job_id, "status": "diarization_todo"}
