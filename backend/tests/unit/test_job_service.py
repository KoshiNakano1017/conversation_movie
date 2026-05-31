"""
job_service のユニットテスト。
DB操作と通知サービスを含むため、関連部分をモックして検証する。
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.models.job import Job, JobStatus
from app.services.job_service import add_job_log, update_job_status


def _insert_job(db_session, job_id: str) -> None:
    db_session.add(Job(
        id=job_id,
        user_id="00000000-0000-0000-0000-000000000001",
        title="テストジョブ",
        status=JobStatus.PENDING,
        progress=0,
        language="ja",
    ))
    db_session.commit()


# ─── update_job_status テスト ─────────────────────────────────────


@patch("app.services.job_service.publish_job_event")
@patch("app.services.job_service.build_job_event", return_value=MagicMock())
def test_update_job_status_updates_db(mock_build, mock_publish, db_session) -> None:
    job_id = str(uuid.uuid4())
    _insert_job(db_session, job_id)

    with patch("app.services.job_service.SessionLocal") as mock_session_cls:
        mock_session_cls.return_value.__enter__ = lambda s: db_session
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        update_job_status(job_id, JobStatus.ANALYZING, progress=30)

    mock_publish.assert_called_once()
    mock_build.assert_called_once_with(
        job_id=job_id,
        status=JobStatus.ANALYZING,
        progress=30,
        error_message=None,
    )


@patch("app.services.job_service.publish_job_event")
@patch("app.services.job_service.build_job_event", return_value=MagicMock())
def test_update_job_status_completed_sets_progress_100(
    mock_build, mock_publish, db_session
) -> None:
    job_id = str(uuid.uuid4())
    _insert_job(db_session, job_id)

    with patch("app.services.job_service.SessionLocal") as mock_session_cls:
        mock_session_cls.return_value.__enter__ = lambda s: db_session
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        update_job_status(job_id, JobStatus.COMPLETED)

    mock_build.assert_called_once_with(
        job_id=job_id,
        status=JobStatus.COMPLETED,
        progress=100,
        error_message=None,
    )


@patch("app.services.job_service.publish_job_event")
@patch("app.services.job_service.build_job_event", return_value=MagicMock())
def test_update_job_status_with_error_message(
    mock_build, mock_publish, db_session
) -> None:
    job_id = str(uuid.uuid4())
    _insert_job(db_session, job_id)

    with patch("app.services.job_service.SessionLocal") as mock_session_cls:
        mock_session_cls.return_value.__enter__ = lambda s: db_session
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        update_job_status(
            job_id,
            JobStatus.FAILED,
            error_message="テストエラーメッセージ",
        )

    mock_build.assert_called_once_with(
        job_id=job_id,
        status=JobStatus.FAILED,
        progress=0,
        error_message="テストエラーメッセージ",
    )


# ─── add_job_log テスト ───────────────────────────────────────────


def test_add_job_log_calls_db_add_and_commit() -> None:
    """add_job_log がDB追加とコミットを正しく呼び出すことを検証"""
    job_id = str(uuid.uuid4())
    mock_db = MagicMock()

    with patch("app.services.job_service.SessionLocal") as mock_session_cls:
        mock_session_cls.return_value.__enter__ = lambda s: mock_db
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        add_job_log(
            job_id=job_id,
            step="test_step",
            message="テストログメッセージ",
            level="error",
            details={"key": "value"},
        )

    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()

    # add に渡された JobLog の内容を検証
    added_log = mock_db.add.call_args[0][0]
    from app.models.job_log import JobLog
    assert isinstance(added_log, JobLog)
    assert added_log.job_id == job_id
    assert added_log.step == "test_step"
    assert added_log.message == "テストログメッセージ"
    assert added_log.level == "error"
    assert added_log.details == {"key": "value"}


def test_add_job_log_default_level_is_info() -> None:
    """level を省略した場合は info がデフォルトになる"""
    job_id = str(uuid.uuid4())
    mock_db = MagicMock()

    with patch("app.services.job_service.SessionLocal") as mock_session_cls:
        mock_session_cls.return_value.__enter__ = lambda s: mock_db
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        add_job_log(job_id=job_id, step="init", message="初期化完了")

    added_log = mock_db.add.call_args[0][0]
    assert added_log.level == "info"
    assert added_log.details == {}
