"""
ジョブのステータス管理・ログ記録を担うサービス。
Celeryワーカーから呼び出され、DBの状態を更新する。
"""

from datetime import datetime, timezone

from loguru import logger
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.job import Job, JobStatus
from app.models.job_log import JobLog
from app.services.notification_service import build_job_event, publish_job_event


def update_job_status(
    job_id: str,
    status: JobStatus,
    progress: int | None = None,
    error_message: str | None = None,
) -> None:
    """
    ジョブのステータスとプログレスをDBに反映する。
    Celeryワーカー内から呼び出すため、セッションを内部で生成する。

    Args:
        job_id: 更新対象のジョブID
        status: 新しいステータス
        progress: 進捗割合（0〜100）。Noneの場合は現在値を維持
        error_message: エラー時のメッセージ
    """
    final_progress = progress if progress is not None else 0

    with SessionLocal() as db:
        updates: dict = {"status": status, "updated_at": datetime.now(timezone.utc)}

        if progress is not None:
            updates["progress"] = progress
            final_progress = progress

        if error_message is not None:
            updates["error_message"] = error_message

        if status == JobStatus.COMPLETED:
            updates["completed_at"] = datetime.now(timezone.utc)
            updates["progress"] = 100
            final_progress = 100

        db.query(Job).filter(Job.id == job_id).update(updates)
        db.commit()

    publish_job_event(
        build_job_event(
            job_id=job_id,
            status=status,
            progress=final_progress,
            error_message=error_message,
        )
    )

    logger.info("ジョブステータス更新", job_id=job_id, status=status.value, progress=progress)


def add_job_log(
    job_id: str,
    step: str,
    message: str,
    level: str = "info",
    details: dict | None = None,
) -> None:
    """
    ジョブの処理ログをDBに記録する。

    Args:
        job_id: 対象のジョブID
        step: 処理ステップ名（例: "gemini_analysis"）
        message: ログメッセージ
        level: ログレベル（"info" / "warning" / "error"）
        details: 追加の詳細情報（JSONB）
    """
    with SessionLocal() as db:
        log_entry = JobLog(
            job_id=job_id,
            level=level,
            step=step,
            message=message,
            details=details or {},
        )
        db.add(log_entry)
        db.commit()
