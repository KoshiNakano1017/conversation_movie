from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.exceptions import AudioValidationError
from app.deps import get_current_user_id, get_db_session
from app.models.audio_file import AudioFile
from app.models.job import Job
from app.services.audio_service import AudioService
from app.workers.pipeline import ConversationPipeline

router = APIRouter(prefix="/api/audio", tags=["audio"])
audio_service = AudioService()


class AudioUploadResponse(BaseModel):
    job_id: str
    status: str
    websocket_url: str


@router.post("/upload", status_code=202, response_model=AudioUploadResponse)
async def upload_audio(
    file: UploadFile = File(...),
    title: str = Form(...),
    description: str | None = Form(default=None),
    language: str = Form(default="ja"),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
) -> AudioUploadResponse:
    """音声またはトランスクリプトファイルを受け取り、処理ジョブを起動する。"""
    file_bytes = await file.read()
    file_size = len(file_bytes)

    try:
        input_kind, extension = audio_service.classify_upload_file(
            filename=file.filename or "",
            content_type=file.content_type,
            file_size_bytes=file_size,
        )

        if input_kind == "audio":
            job_id = audio_service.create_job_and_audio_record(
                db=db,
                user_id=user_id,
                title=title.strip(),
                description=description,
                language=language,
                original_filename=file.filename or "upload",
                storage_path="",
                file_size_bytes=file_size,
                file_format=extension,
            )

            local_path = audio_service.save_audio_bytes(
                job_id=job_id,
                original_filename=file.filename or f"audio{extension}",
                file_bytes=file_bytes,
            )

            # storage_path を保存パスで更新
            db.query(AudioFile).filter(AudioFile.job_id == job_id).update({"storage_path": str(local_path)})
            task_id = ConversationPipeline.start_from_audio(job_id)
            response_status = "queued"
            logger.info("音声アップロード受付完了", job_id=job_id, filename=file.filename, size=file_size)
        else:
            transcript_text = audio_service.decode_transcript_bytes(file_bytes)
            job_id = audio_service.create_job_and_transcription_record(
                db=db,
                user_id=user_id,
                title=title.strip(),
                description=description,
                language=language,
                transcript_text=transcript_text,
            )
            task_id = ConversationPipeline.start_from_transcript(job_id)
            response_status = "analyzing"
            logger.info("トランスクリプトアップロード受付完了", job_id=job_id, filename=file.filename)

        db.query(Job).filter(Job.id == job_id).update({"celery_task_id": task_id})
        db.commit()

        return AudioUploadResponse(
            job_id=job_id,
            status=response_status,
            websocket_url=f"/ws/jobs/{job_id}",
        )
    except AudioValidationError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error.to_dict(),
        ) from error
    except Exception as error:
        db.rollback()
        logger.exception("音声アップロード処理失敗", error=str(error))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="音声アップロード処理に失敗しました",
        ) from error
