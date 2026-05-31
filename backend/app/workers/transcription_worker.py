from celery import Task
from loguru import logger

from app.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.exceptions import TranscriptionError
from app.models.audio_file import AudioFile
from app.models.job import Job, JobStatus
from app.models.transcription import Transcription
from app.services.job_service import add_job_log, update_job_status
from app.services.transcription_service import TranscriptionService


@celery_app.task(
    name="workers.transcription",
    queue="ai",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def run_transcription_task(self: Task, job_id: str) -> dict:
    """
    Whisperを使って音声ファイルを文字起こしするタスク。
    """
    logger.info("文字起こしタスク開始", job_id=job_id)
    update_job_status(job_id, JobStatus.TRANSCRIBING, progress=20)

    try:
        job, audio_file = _fetch_job_and_audio(job_id)
        add_job_log(job_id, "transcription", "文字起こし対象の音声ファイル取得完了")

        service = TranscriptionService()
        result = service.transcribe_audio_file(audio_file.storage_path, language=job.language)

        _save_transcription(
            job_id=job_id,
            language=result["language"],
            text=result["text"],
            segments=result["segments"],
        )
        _mark_audio_processed(job_id)

        add_job_log(
            job_id,
            "transcription",
            "文字起こし完了",
            details={
                "language": result["language"],
                "segments": len(result["segments"]),
                "characters": len(result["text"]),
            },
        )
        update_job_status(job_id, JobStatus.ANALYZING, progress=35)

        return {
            "job_id": job_id,
            "status": "transcription_completed",
            "language": result["language"],
            "segments_count": len(result["segments"]),
        }
    except TranscriptionError as error:
        _handle_failure(job_id, error, "transcription")
        raise
    except Exception as error:
        _handle_failure(job_id, error, "transcription_unexpected")
        raise


def _fetch_job_and_audio(job_id: str) -> tuple[Job, AudioFile]:
    with SessionLocal() as db:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise TranscriptionError(code="TRN006", message=f"ジョブが見つかりません: {job_id}")

        audio_file = db.query(AudioFile).filter(AudioFile.job_id == job_id).first()
        if not audio_file:
            raise TranscriptionError(code="TRN007", message=f"音声ファイルが見つかりません: {job_id}")

        return job, audio_file


def _save_transcription(job_id: str, language: str, text: str, segments: list[dict]) -> None:
    with SessionLocal() as db:
        existing = db.query(Transcription).filter(Transcription.job_id == job_id).first()
        if existing:
            existing.full_text = text
            existing.language = language
            existing.source = "whisper"
            existing.segments = segments
        else:
            db.add(
                Transcription(
                    job_id=job_id,
                    full_text=text,
                    language=language,
                    source="whisper",
                    segments=segments,
                )
            )
        db.commit()


def _mark_audio_processed(job_id: str) -> None:
    with SessionLocal() as db:
        db.query(AudioFile).filter(AudioFile.job_id == job_id).update({"is_processed": True})
        db.commit()


def _handle_failure(job_id: str, error: Exception, step: str) -> None:
    logger.error("文字起こしタスク失敗", job_id=job_id, step=step, error=str(error))
    add_job_log(job_id, step, str(error), level="error")
    update_job_status(
        job_id,
        JobStatus.FAILED,
        error_message=f"[{step}] {str(error)}",
    )
