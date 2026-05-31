from pathlib import Path

from fastapi.testclient import TestClient

from app.api.audio import audio_service
from app.models.transcription import Transcription


def test_audio_upload_success(client: TestClient, mocker, tmp_path: Path) -> None:
    mocker.patch("app.api.audio.ConversationPipeline.start_from_audio", return_value="task-123")
    audio_service.media_dir = tmp_path

    response = client.post(
        "/api/audio/upload",
        data={
            "title": "定例ミーティング",
            "description": "週次報告",
            "language": "ja",
        },
        files={"file": ("meeting.mp3", b"dummy-audio", "audio/mpeg")},
    )

    assert response.status_code == 202
    body = response.json()
    assert "job_id" in body
    assert body["status"] == "queued"
    assert body["websocket_url"].endswith(body["job_id"])
    assert (tmp_path / "audio" / body["job_id"] / "meeting.mp3").exists()


def test_audio_upload_rejects_invalid_file_type(client: TestClient) -> None:
    response = client.post(
        "/api/audio/upload",
        data={"title": "invalid file"},
        files={"file": ("notes.pdf", b"not-audio", "application/pdf")},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["detail"]["code"] == "AUD002"


def test_transcript_upload_success(client: TestClient, db_session, mocker) -> None:
    mocker.patch("app.api.audio.ConversationPipeline.start_from_transcript", return_value="task-234")

    payload = "山田：本日の進捗を共有します。\n鈴木：次のタスクを確認します。"
    response = client.post(
        "/api/audio/upload",
        data={"title": "議事録アップロード", "language": "ja"},
        files={"file": ("meeting.txt", payload.encode("utf-8"), "text/plain")},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "analyzing"

    transcript = db_session.query(Transcription).filter(Transcription.job_id == body["job_id"]).first()
    assert transcript is not None
    assert transcript.source == "upload"
    assert "本日の進捗" in transcript.full_text
