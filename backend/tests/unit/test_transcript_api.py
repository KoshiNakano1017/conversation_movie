"""
transcript.py API エンドポイントのテスト。
POST /api/transcript/paste
GET  /api/transcript/{job_id}
"""

import uuid

from fastapi.testclient import TestClient

from app.deps import DEV_USER_ID
from app.models.job import Job, JobStatus
from app.models.transcription import Transcription


# ─── POST /api/transcript/paste ───────────────────────────────────


def test_paste_transcript_success(client: TestClient, db_session, mocker) -> None:
    mocker.patch(
        "app.api.transcript.ConversationPipeline.start_from_transcript",
        return_value="task-paste-001",
    )

    response = client.post(
        "/api/transcript/paste",
        json={
            "title": "週次定例MTG",
            "text": "山田：今週の進捗を共有します。鈴木：了解しました。田中：確認できました。",
            "language": "ja",
            "description": "テスト用MTG",
        },
    )

    assert response.status_code == 202
    body = response.json()
    assert "job_id" in body
    assert body["status"] == "analyzing"
    assert body["character_count"] > 10
    assert "/ws/jobs/" in body["websocket_url"]


def test_paste_transcript_too_short(client: TestClient) -> None:
    """10文字未満のテキストは拒否される"""
    response = client.post(
        "/api/transcript/paste",
        json={
            "title": "短いテキスト",
            "text": "短すぎ",
            "language": "ja",
        },
    )
    assert response.status_code == 422


def test_paste_transcript_saves_to_db(client: TestClient, db_session, mocker) -> None:
    mocker.patch(
        "app.api.transcript.ConversationPipeline.start_from_transcript",
        return_value="task-save-001",
    )

    text = "山田：これはDBに保存されるべきトランスクリプトです。内容は十分長くなっています。"
    response = client.post(
        "/api/transcript/paste",
        json={"title": "保存テスト", "text": text, "language": "en"},
    )

    assert response.status_code == 202
    job_id = response.json()["job_id"]

    transcript = db_session.query(Transcription).filter(
        Transcription.job_id == job_id
    ).first()
    assert transcript is not None
    assert transcript.source == "paste"
    assert transcript.language == "en"
    assert text.strip() == transcript.full_text


# ─── GET /api/transcript/{job_id} ────────────────────────────────


def test_get_transcript_by_job_id(client: TestClient, db_session) -> None:
    job_id = str(uuid.uuid4())
    db_session.add(Job(
        id=job_id,
        user_id=DEV_USER_ID,
        title="取得テスト",
        status=JobStatus.COMPLETED,
        progress=100,
        language="ja",
    ))
    db_session.add(Transcription(
        id=str(uuid.uuid4()),
        job_id=job_id,
        full_text="取得用のテキストです。",
        language="ja",
        source="paste",
        segments=[],
    ))
    db_session.commit()

    response = client.get(f"/api/transcript/{job_id}")
    assert response.status_code == 200

    body = response.json()
    assert body["job_id"] == job_id
    assert "取得用のテキスト" in body["full_text"]
    assert body["source"] == "paste"
    assert "character_count" in body


def test_get_transcript_not_found(client: TestClient) -> None:
    response = client.get(f"/api/transcript/{uuid.uuid4()}")
    assert response.status_code == 404
