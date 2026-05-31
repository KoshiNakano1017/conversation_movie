"""
StorageService のユニットテスト。
外部依存なし（ファイルパス・URLの生成ロジックのみ）。
"""

from pathlib import Path

import pytest

from app.services.storage_service import StorageService


@pytest.fixture
def service(tmp_path: Path) -> StorageService:
    svc = StorageService()
    svc.media_dir = tmp_path
    return svc


# ─── URL生成テスト ────────────────────────────────────────────────


def test_get_video_url_format(service: StorageService) -> None:
    url = service.get_video_url("job-123", "full.mp4")
    assert url == "/media/video/job-123/full.mp4"


def test_get_thumbnail_url_format(service: StorageService) -> None:
    url = service.get_thumbnail_url("job-456")
    assert url == "/media/video/job-456/thumbnail.jpg"


def test_get_video_local_path(service: StorageService, tmp_path: Path) -> None:
    path = service.get_video_local_path("job-789", "output.mp4")
    assert path == tmp_path / "video" / "job-789" / "output.mp4"


# ─── クリーンアップテスト ─────────────────────────────────────────


def test_cleanup_temp_files_removes_non_final(service: StorageService, tmp_path: Path) -> None:
    job_id = "cleanup-job-001"
    job_dir = tmp_path / "video" / job_id
    job_dir.mkdir(parents=True)

    # 最終ファイルと一時ファイルを作成
    (job_dir / "full.mp4").write_bytes(b"final")
    (job_dir / "thumbnail.jpg").write_bytes(b"thumb")
    (job_dir / "video_data.json").write_bytes(b"temp")
    (job_dir / "subtitles.srt").write_bytes(b"srt")

    service.cleanup_temp_files(job_id, keep_final=True)

    assert (job_dir / "full.mp4").exists()
    assert (job_dir / "thumbnail.jpg").exists()
    assert not (job_dir / "video_data.json").exists()
    assert not (job_dir / "subtitles.srt").exists()


def test_cleanup_temp_files_removes_all_when_keep_false(
    service: StorageService, tmp_path: Path
) -> None:
    job_id = "cleanup-job-002"
    job_dir = tmp_path / "video" / job_id
    job_dir.mkdir(parents=True)

    (job_dir / "full.mp4").write_bytes(b"final")
    (job_dir / "video_data.json").write_bytes(b"temp")

    service.cleanup_temp_files(job_id, keep_final=False)

    assert not (job_dir / "full.mp4").exists()
    assert not (job_dir / "video_data.json").exists()


def test_cleanup_nonexistent_job_is_noop(service: StorageService) -> None:
    """存在しないジョブIDでクリーンアップしてもエラーにならない"""
    service.cleanup_temp_files("nonexistent-job-id")


# ─── Supabaseスキップテスト ───────────────────────────────────────


def test_upload_to_supabase_skips_when_not_configured(
    service: StorageService, tmp_path: Path, monkeypatch
) -> None:
    """Supabase未設定の場合はローカルパスを返す"""
    monkeypatch.setattr("app.services.storage_service.settings.SUPABASE_URL", "")

    test_file = tmp_path / "test.mp4"
    test_file.write_bytes(b"fake video")

    result = service.upload_to_supabase(test_file, "test/test.mp4")
    assert result == str(test_file)
