from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.deps import get_current_user_id, get_db_session
from app.models.analysis import Analysis
from app.models.audio_file import AudioFile
from app.models.job import JOB_STATUS_PROGRESS, Job, JobStatus
from app.models.transcription import Transcription
from app.models.video import Video
from app.workers.pipeline import ConversationPipeline

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


class JobListItem(BaseModel):
    id: str
    title: str
    status: str
    progress: int
    created_at: str
    updated_at: str
    completed_at: str | None


class JobListResponse(BaseModel):
    jobs: list[JobListItem]
    total: int
    page: int
    page_size: int


class JobDetailResponse(BaseModel):
    id: str
    title: str
    description: str | None
    status: str
    progress: int
    language: str
    error_message: str | None
    celery_task_id: str | None
    created_at: str
    updated_at: str
    completed_at: str | None
    has_audio: bool
    has_transcript: bool
    has_analysis: bool
    has_video: bool
    latest_video_path: str | None


class JobRetryResponse(BaseModel):
    job_id: str
    status: str
    task_id: str


def _to_iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


@router.get("/{job_id}")
def get_job(
    job_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
) -> JobDetailResponse:
    """ジョブ詳細を返す。"""
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == user_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ジョブが見つかりません")

    latest_video = (
        db.query(Video).filter(Video.job_id == job_id).order_by(Video.created_at.desc()).first()
    )
    has_audio = db.query(AudioFile.id).filter(AudioFile.job_id == job_id).first() is not None
    has_transcript = db.query(Transcription.id).filter(Transcription.job_id == job_id).first() is not None
    has_analysis = db.query(Analysis.id).filter(Analysis.job_id == job_id).first() is not None

    return JobDetailResponse(
        id=job.id,
        title=job.title,
        description=job.description,
        status=job.status.value,
        progress=job.progress,
        language=job.language,
        error_message=job.error_message,
        celery_task_id=job.celery_task_id,
        created_at=job.created_at.isoformat(),
        updated_at=job.updated_at.isoformat(),
        completed_at=_to_iso(job.completed_at),
        has_audio=has_audio,
        has_transcript=has_transcript,
        has_analysis=has_analysis,
        has_video=latest_video is not None,
        latest_video_path=latest_video.storage_path if latest_video else None,
    )


@router.get("", response_model=JobListResponse)
def list_jobs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
) -> JobListResponse:
    """ログインユーザーのジョブ一覧をページネーション付きで返す。"""
    base_query = db.query(Job).filter(Job.user_id == user_id)
    total = base_query.with_entities(func.count(Job.id)).scalar() or 0

    jobs = (
        base_query.order_by(Job.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return JobListResponse(
        jobs=[
            JobListItem(
                id=job.id,
                title=job.title,
                status=job.status.value,
                progress=job.progress,
                created_at=job.created_at.isoformat(),
                updated_at=job.updated_at.isoformat(),
                completed_at=_to_iso(job.completed_at),
            )
            for job in jobs
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.delete("/{job_id}")
def delete_job(
    job_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
) -> dict:
    """指定ジョブを削除する。"""
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == user_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ジョブが見つかりません")

    db.delete(job)
    db.commit()
    return {"deleted": True, "job_id": job_id}


@router.post("/{job_id}/retry", response_model=JobRetryResponse)
def retry_job(
    job_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
) -> JobRetryResponse:
    """失敗/キャンセルしたジョブを再実行する。"""
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == user_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ジョブが見つかりません")

    if job.status not in {JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.COMPLETED}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="このジョブは再実行できる状態ではありません",
        )

    transcript = db.query(Transcription).filter(Transcription.job_id == job_id).first()
    audio = db.query(AudioFile).filter(AudioFile.job_id == job_id).first()

    if transcript and transcript.source == "paste":
        new_status = JobStatus.ANALYZING
        task_id = ConversationPipeline.start_from_transcript(job_id)
    elif audio:
        new_status = JobStatus.TRANSCRIBING
        task_id = ConversationPipeline.start_from_audio(job_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="再実行に必要な入力データが見つかりません",
        )

    job.status = new_status
    job.progress = JOB_STATUS_PROGRESS[new_status]
    job.error_message = None
    job.completed_at = None
    job.celery_task_id = task_id
    db.commit()

    return JobRetryResponse(job_id=job_id, status=new_status.value, task_id=task_id)
