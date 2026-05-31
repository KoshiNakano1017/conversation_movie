import uuid

from fastapi.testclient import TestClient

from app.deps import DEV_USER_ID
from app.models.analysis import Analysis
from app.models.audio_file import AudioFile
from app.models.job import Job, JobStatus
from app.models.transcription import Transcription
from app.models.video import Video, VideoType


def _create_job(db_session, title: str, status: JobStatus = JobStatus.PENDING) -> str:
    job_id = str(uuid.uuid4())
    job = Job(
        id=job_id,
        user_id=DEV_USER_ID,
        title=title,
        status=status,
        progress=0,
        language="ja",
    )
    db_session.add(job)
    db_session.commit()
    return job_id


def test_list_jobs_returns_paginated_items(client: TestClient, db_session) -> None:
    _create_job(db_session, "job-1")
    _create_job(db_session, "job-2")
    _create_job(db_session, "job-3")

    response = client.get("/api/jobs?page=1&page_size=2")
    assert response.status_code == 200

    body = response.json()
    assert body["total"] >= 3
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert len(body["jobs"]) == 2


def test_get_job_returns_related_flags(client: TestClient, db_session) -> None:
    job_id = _create_job(db_session, "detail-target", status=JobStatus.COMPLETED)

    db_session.add(
        Transcription(
            id=str(uuid.uuid4()),
            job_id=job_id,
            full_text="これはテスト用トランスクリプトです",
            language="ja",
            source="paste",
            segments=[],
        )
    )
    db_session.add(
        Analysis(
            id=str(uuid.uuid4()),
            job_id=job_id,
            summary_short="短い要約",
            summary_medium="中くらいの要約",
            summary_detailed={},
            themes=["a"],
            keywords=["k"],
            quotes=[],
            sentiment_timeline=[],
            overall_sentiment="neutral",
            suggested_title="title",
            suggested_description="desc",
            suggested_tags=["tag"],
        )
    )
    db_session.add(
        Video(
            id=str(uuid.uuid4()),
            job_id=job_id,
            user_id=DEV_USER_ID,
            video_type=VideoType.FULL,
            storage_path="/media/video/test.mp4",
            storage_bucket="videos",
        )
    )
    db_session.commit()

    response = client.get(f"/api/jobs/{job_id}")
    assert response.status_code == 200

    body = response.json()
    assert body["id"] == job_id
    assert body["has_transcript"] is True
    assert body["has_analysis"] is True
    assert body["has_video"] is True
    assert body["latest_video_path"] == "/media/video/test.mp4"


def test_delete_job_removes_record(client: TestClient, db_session) -> None:
    job_id = _create_job(db_session, "delete-target")

    response = client.delete(f"/api/jobs/{job_id}")
    assert response.status_code == 200
    assert response.json() == {"deleted": True, "job_id": job_id}

    assert db_session.query(Job).filter(Job.id == job_id).first() is None


def test_retry_job_from_transcript(client: TestClient, db_session, mocker) -> None:
    job_id = _create_job(db_session, "retry-transcript", status=JobStatus.FAILED)
    db_session.add(
        Transcription(
            id=str(uuid.uuid4()),
            job_id=job_id,
            full_text="再実行用テキストです",
            language="ja",
            source="paste",
            segments=[],
        )
    )
    db_session.commit()

    mocker.patch("app.api.jobs.ConversationPipeline.start_from_transcript", return_value="task-retry-1")

    response = client.post(f"/api/jobs/{job_id}/retry")
    assert response.status_code == 200

    body = response.json()
    assert body["job_id"] == job_id
    assert body["status"] == "analyzing"
    assert body["task_id"] == "task-retry-1"


def test_retry_job_rejects_when_no_source_data(client: TestClient, db_session) -> None:
    job_id = _create_job(db_session, "retry-invalid", status=JobStatus.FAILED)

    response = client.post(f"/api/jobs/{job_id}/retry")
    assert response.status_code == 400


def test_retry_job_from_audio(client: TestClient, db_session, mocker) -> None:
    job_id = _create_job(db_session, "retry-audio", status=JobStatus.CANCELLED)
    db_session.add(
        AudioFile(
            id=str(uuid.uuid4()),
            job_id=job_id,
            user_id=DEV_USER_ID,
            original_filename="meeting.mp3",
            storage_path="/tmp/meeting.mp3",
            storage_bucket="audio",
            file_size_bytes=1234,
            format="mp3",
            is_processed=False,
        )
    )
    db_session.commit()

    mocker.patch("app.api.jobs.ConversationPipeline.start_from_audio", return_value="task-retry-2")

    response = client.post(f"/api/jobs/{job_id}/retry")
    assert response.status_code == 200
    assert response.json()["status"] == "transcribing"


def test_retry_job_rejects_running_status(client: TestClient, db_session) -> None:
    job_id = _create_job(db_session, "retry-running", status=JobStatus.ANALYZING)
    response = client.post(f"/api/jobs/{job_id}/retry")
    assert response.status_code == 409
