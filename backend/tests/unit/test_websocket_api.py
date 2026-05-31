import uuid

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.deps import DEV_USER_ID
from app.models.job import Job, JobStatus


def _create_job(db_session, status: JobStatus, progress: int, user_id: str = DEV_USER_ID) -> str:
    job_id = str(uuid.uuid4())
    db_session.add(
        Job(
            id=job_id,
            user_id=user_id,
            title="ws-test",
            status=status,
            progress=progress,
            language="ja",
        )
    )
    db_session.commit()
    return job_id


def test_websocket_sends_initial_progress_event(client: TestClient, db_session) -> None:
    job_id = _create_job(db_session, status=JobStatus.ANALYZING, progress=25)

    with client.websocket_connect(f"/ws/jobs/{job_id}") as websocket:
        payload = websocket.receive_json()

    assert payload["event"] == "job_progress"
    assert payload["data"]["progress"] == 25
    assert payload["data"]["step"] == "analyzing"
    assert payload["data"]["status"] == "in_progress"


def test_websocket_sends_failed_event(client: TestClient, db_session) -> None:
    job_id = _create_job(db_session, status=JobStatus.FAILED, progress=30)

    with client.websocket_connect(f"/ws/jobs/{job_id}") as websocket:
        payload = websocket.receive_json()

    assert payload["event"] == "job_failed"
    assert payload["data"]["current_status"] == "failed"


def test_websocket_rejects_non_owner(client: TestClient, db_session) -> None:
    another_user_id = str(uuid.uuid4())
    job_id = _create_job(db_session, status=JobStatus.ANALYZING, progress=10, user_id=another_user_id)

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/jobs/{job_id}"):
            pass
