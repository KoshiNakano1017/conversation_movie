from pathlib import Path

import pytest

from app.core.exceptions import AudioValidationError
from app.services.audio_service import AudioService


def test_validate_file_metadata_accepts_supported_audio() -> None:
    service = AudioService(media_dir=".")

    extension, content_type = service.validate_file_metadata(
        filename="meeting.mp3",
        content_type="audio/mpeg",
        file_size_bytes=1024,
    )

    assert extension == ".mp3"
    assert content_type == "audio/mpeg"


def test_validate_file_metadata_rejects_unsupported_extension() -> None:
    service = AudioService(media_dir=".")

    with pytest.raises(AudioValidationError) as error:
        service.validate_file_metadata(
            filename="meeting.txt",
            content_type="text/plain",
            file_size_bytes=100,
        )

    assert error.value.code == "AUD002"


def test_validate_file_metadata_rejects_oversized_file() -> None:
    service = AudioService(media_dir=".")

    with pytest.raises(AudioValidationError) as error:
        service.validate_file_metadata(
            filename="meeting.wav",
            content_type="audio/wav",
            file_size_bytes=1024 * 1024 * 1024,
        )

    assert error.value.code == "AUD005"


def test_save_audio_bytes_writes_file(tmp_path: Path) -> None:
    service = AudioService(media_dir=str(tmp_path))
    payload = b"dummy-audio-data"

    saved_path = service.save_audio_bytes(
        job_id="job-123",
        original_filename="meeting.m4a",
        file_bytes=payload,
    )

    assert saved_path.exists()
    assert saved_path.read_bytes() == payload
    assert saved_path == tmp_path / "audio" / "job-123" / "meeting.m4a"
