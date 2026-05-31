from pathlib import Path
import uuid

from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import AudioValidationError
from app.models.audio_file import AudioFile
from app.models.job import JOB_STATUS_PROGRESS, Job, JobStatus
from app.models.transcription import Transcription


class AudioService:
    """音声アップロードのバリデーションと保存を担当するサービス"""

    TRANSCRIPT_EXTENSIONS = {".txt", ".md", ".srt", ".vtt"}
    TRANSCRIPT_CONTENT_TYPES = {
        "text/plain",
        "text/markdown",
        "application/octet-stream",  # ブラウザ依存で text が octet-stream になるケース
    }

    def __init__(self, media_dir: str | None = None) -> None:
        self.media_dir = Path(media_dir or settings.MEDIA_DIR)

    def validate_file_metadata(
        self,
        filename: str,
        content_type: str | None,
        file_size_bytes: int,
    ) -> tuple[str, str]:
        """
        ファイル情報を検証し、拡張子とMIMEタイプを返す。
        """
        sanitized_name = Path(filename).name
        extension = Path(sanitized_name).suffix.lower()
        content_type_value = content_type or ""

        if not sanitized_name or not extension:
            raise AudioValidationError(
                code="AUD001",
                message="ファイル名または拡張子が不正です",
            )

        if extension not in settings.allowed_audio_extensions:
            raise AudioValidationError(
                code="AUD002",
                message=f"未対応のファイル形式です: {extension}",
            )

        if content_type_value and content_type_value not in settings.allowed_audio_content_types:
            raise AudioValidationError(
                code="AUD003",
                message=f"未対応のContent-Typeです: {content_type_value}",
            )

        if file_size_bytes <= 0:
            raise AudioValidationError(
                code="AUD004",
                message="空ファイルはアップロードできません",
            )

        if file_size_bytes > settings.max_upload_size_bytes:
            raise AudioValidationError(
                code="AUD005",
                message=(
                    f"ファイルサイズ上限を超えています: {settings.MAX_UPLOAD_SIZE_MB}MB 以下にしてください"
                ),
            )

        return extension, content_type_value

    def classify_upload_file(
        self,
        filename: str,
        content_type: str | None,
        file_size_bytes: int,
    ) -> tuple[str, str]:
        """
        アップロード入力が audio / transcript のどちらかを判定する。

        Returns:
            (kind, extension)  kind は "audio" または "transcript"
        """
        sanitized_name = Path(filename).name
        extension = Path(sanitized_name).suffix.lower()
        content_type_value = content_type or ""

        if not sanitized_name or not extension:
            raise AudioValidationError(
                code="AUD001",
                message="ファイル名または拡張子が不正です",
            )

        if file_size_bytes <= 0:
            raise AudioValidationError(
                code="AUD004",
                message="空ファイルはアップロードできません",
            )

        if file_size_bytes > settings.max_upload_size_bytes:
            raise AudioValidationError(
                code="AUD005",
                message=(
                    f"ファイルサイズ上限を超えています: {settings.MAX_UPLOAD_SIZE_MB}MB 以下にしてください"
                ),
            )

        if extension in settings.allowed_audio_extensions:
            if content_type_value and content_type_value not in settings.allowed_audio_content_types:
                raise AudioValidationError(
                    code="AUD003",
                    message=f"未対応のContent-Typeです: {content_type_value}",
                )
            return "audio", extension

        if extension in self.TRANSCRIPT_EXTENSIONS:
            if content_type_value and content_type_value not in self.TRANSCRIPT_CONTENT_TYPES:
                raise AudioValidationError(
                    code="AUD003",
                    message=f"未対応のContent-Typeです: {content_type_value}",
                )
            return "transcript", extension

        raise AudioValidationError(
            code="AUD002",
            message=f"未対応のファイル形式です: {extension}",
        )

    def decode_transcript_bytes(self, file_bytes: bytes) -> str:
        """トランスクリプトファイルのバイト列を文字列へデコードする。"""
        for encoding in ("utf-8-sig", "utf-16", "cp932"):
            try:
                decoded = file_bytes.decode(encoding)
                return decoded.strip()
            except UnicodeDecodeError:
                continue
        raise AudioValidationError(
            code="AUD006",
            message="トランスクリプトファイルの文字コードを判別できません",
        )

    def save_audio_bytes(self, job_id: str, original_filename: str, file_bytes: bytes) -> Path:
        """
        音声ファイルをローカル保存し、保存パスを返す。
        """
        audio_dir = self.media_dir / "audio" / job_id
        audio_dir.mkdir(parents=True, exist_ok=True)

        filename = Path(original_filename).name
        output_path = audio_dir / filename
        output_path.write_bytes(file_bytes)
        return output_path

    def create_job_and_audio_record(
        self,
        db: Session,
        user_id: str,
        title: str,
        description: str | None,
        language: str,
        original_filename: str,
        storage_path: str,
        file_size_bytes: int,
        file_format: str,
    ) -> str:
        """
        jobs と audio_files レコードを作成し、job_idを返す。
        """
        job_id = str(uuid.uuid4())

        job = Job(
            id=job_id,
            user_id=user_id,
            title=title,
            description=description,
            status=JobStatus.UPLOADING,
            progress=JOB_STATUS_PROGRESS[JobStatus.UPLOADING],
            language=language,
        )

        audio = AudioFile(
            job_id=job_id,
            user_id=user_id,
            original_filename=Path(original_filename).name,
            storage_path=storage_path,
            storage_bucket="audio",
            file_size_bytes=file_size_bytes,
            format=file_format.lstrip("."),
            is_processed=False,
        )

        db.add(job)
        db.add(audio)
        db.flush()
        return job_id

    def create_job_and_transcription_record(
        self,
        db: Session,
        user_id: str,
        title: str,
        description: str | None,
        language: str,
        transcript_text: str,
    ) -> str:
        """
        jobs と transcriptions レコードを作成し、job_idを返す。
        """
        cleaned = transcript_text.strip()
        if len(cleaned) < 10:
            raise AudioValidationError(
                code="AUD007",
                message="トランスクリプトが短すぎます（10文字以上必要です）",
            )

        job_id = str(uuid.uuid4())
        job = Job(
            id=job_id,
            user_id=user_id,
            title=title,
            description=description,
            status=JobStatus.ANALYZING,
            progress=10,
            language=language,
        )
        transcription = Transcription(
            job_id=job_id,
            full_text=cleaned,
            language=language,
            source="upload",
            segments=[],
        )

        db.add(job)
        db.add(transcription)
        db.flush()
        return job_id
