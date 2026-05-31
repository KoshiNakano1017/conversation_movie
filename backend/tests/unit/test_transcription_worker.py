import uuid

import pytest
from sqlalchemy.orm import sessionmaker

from app.deps import DEV_USER_ID
from app.models.audio_file import AudioFile
from app.models.job import Job, JobStatus
from app.models.transcription import Transcription
from app.workers import transcription_worker


def _make_session_factory(db_session):
    return sessionmaker(autocommit=False, autoflush=False, bind=db_session.bind)


def test_run_transcription_task_saves_transcription(db_session, mocker) -> None:
    job_id = str(uuid.uuid4())
    db_session.add(
        Job(
            id=job_id,
            user_id=DEV_USER_ID,
            title="audio transcription",
            status=JobStatus.UPLOADING,
            progress=5,
            language="ja",
        )
    )
    db_session.add(
        AudioFile(
            id=str(uuid.uuid4()),
            job_id=job_id,
            user_id=DEV_USER_ID,
            original_filename="meeting.mp3",
            storage_path="C:/tmp/meeting.mp3",
            storage_bucket="audio",
            file_size_bytes=1234,
            format="mp3",
            is_processed=False,
        )
    )
    db_session.commit()

    mocker.patch.object(transcription_worker, "SessionLocal", _make_session_factory(db_session))
    mocker.patch.object(transcription_worker, "add_job_log")
    mocker.patch.object(transcription_worker, "update_job_status")
    mocker.patch.object(
        transcription_worker.TranscriptionService,
        "transcribe_audio_file",
        return_value={
            "text": "山田：こんにちは\n鈴木：よろしくお願いします",
            "language": "ja",
            "segments": [
                {"id": 0, "start": 0.0, "end": 1.2, "text": "山田：こんにちは", "speaker": ""},
                {"id": 1, "start": 1.2, "end": 2.8, "text": "鈴木：よろしくお願いします", "speaker": ""},
            ],
        },
    )

    result = transcription_worker.run_transcription_task.run(job_id)  # type: ignore[attr-defined]

    assert result["status"] == "transcription_completed"
    record = db_session.query(Transcription).filter(Transcription.job_id == job_id).first()
    assert record is not None
    assert record.source == "whisper"
    assert len(record.segments) == 2


def test_run_transcription_task_raises_when_audio_missing(db_session, mocker) -> None:
    job_id = str(uuid.uuid4())
    db_session.add(
        Job(
            id=job_id,
            user_id=DEV_USER_ID,
            title="audio missing",
            status=JobStatus.UPLOADING,
            progress=5,
            language="ja",
        )
    )
    db_session.commit()

    mocker.patch.object(transcription_worker, "SessionLocal", _make_session_factory(db_session))
    mocker.patch.object(transcription_worker, "add_job_log")
    mocker.patch.object(transcription_worker, "update_job_status")

    with pytest.raises(Exception):
        transcription_worker.run_transcription_task.run(job_id)  # type: ignore[attr-defined]
