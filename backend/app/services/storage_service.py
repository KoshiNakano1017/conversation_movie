"""
ファイルのストレージ管理サービス。

MVP段階の方針:
- 生成ファイルはローカルの /app/media/ に保存
- Supabase Storageへのアップロードはオプション（環境変数で制御）
- ローカルファイルの署名付きURL生成にはFastAPIの静的ファイル配信を使用
"""

from pathlib import Path

from loguru import logger

from app.config import settings
from app.core.exceptions import StorageError


class StorageService:
    """ローカルストレージとSupabase Storageの両方を管理するサービス"""

    def __init__(self) -> None:
        self.media_dir = Path(settings.MEDIA_DIR)

    def get_video_local_path(self, job_id: str, filename: str) -> Path:
        """ジョブの動画ファイルのローカルパスを返す"""
        return self.media_dir / "video" / job_id / filename

    def get_video_url(self, job_id: str, filename: str) -> str:
        """
        動画ファイルへのアクセスURLを返す。
        MVP段階ではローカルのAPIサーバー経由でファイルを配信する。
        """
        return f"/media/video/{job_id}/{filename}"

    def get_thumbnail_url(self, job_id: str) -> str:
        """サムネイルへのアクセスURLを返す"""
        return f"/media/video/{job_id}/thumbnail.jpg"

    def upload_to_supabase(
        self,
        local_path: Path,
        storage_path: str,
        bucket: str = "videos",
        content_type: str = "video/mp4",
    ) -> str:
        """
        ローカルファイルをSupabase Storageにアップロードする。
        Supabase設定がない場合はスキップしてローカルURLを返す。

        Args:
            local_path: アップロードするローカルファイルのパス
            storage_path: Supabase Storage内のパス（例: "user_id/job_id/full.mp4"）
            bucket: Supabaseのバケット名
            content_type: MIMEタイプ

        Returns:
            アクセス可能な公開URL
        """
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
            logger.info("Supabase未設定のためローカル配信を使用", path=str(local_path))
            return str(local_path)

        try:
            from app.core.supabase_client import get_supabase_admin_client

            client = get_supabase_admin_client()
            file_bytes = local_path.read_bytes()

            client.storage.from_(bucket).upload(
                path=storage_path,
                file=file_bytes,
                file_options={"content-type": content_type, "upsert": "true"},
            )

            public_url_response = client.storage.from_(bucket).get_public_url(storage_path)
            logger.info("Supabaseアップロード完了", path=storage_path, bucket=bucket)
            return public_url_response

        except Exception as error:
            logger.warning(
                "Supabaseアップロード失敗（ローカルにフォールバック）",
                error=str(error),
            )
            return str(local_path)

    def upload_audio_public(self, job_id: str, audio_path: Path) -> str:
        """
        TTS 音声ファイルを Supabase Storage の公開バケットにアップロードし、
        Shotstack が HTTP アクセス可能な公開 URL を返す。

        Supabase 未設定時はローカルパス文字列を返す（Shotstack は使えないが処理は継続する）。

        Args:
            job_id: ジョブID（ストレージパスのプレフィックス）
            audio_path: アップロードするローカル音声ファイルのパス

        Returns:
            公開 URL（例: https://<project>.supabase.co/storage/v1/object/public/audio/...）
        """
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
            logger.warning(
                "Supabase 未設定のため音声を公開アップロードできません。TTS なしで続行します。",
                path=str(audio_path),
            )
            return str(audio_path)

        storage_path = f"{job_id}/{audio_path.name}"
        try:
            from app.core.supabase_client import get_supabase_admin_client

            client = get_supabase_admin_client()
            file_bytes = audio_path.read_bytes()

            client.storage.from_("audio").upload(
                path=storage_path,
                file=file_bytes,
                file_options={"content-type": "audio/mpeg", "upsert": "true"},
            )

            public_url: str = client.storage.from_("audio").get_public_url(storage_path)
            logger.info("音声ファイルを公開アップロード完了", path=storage_path)
            return public_url

        except Exception as error:
            logger.warning(
                "音声の公開アップロード失敗。TTS なしで続行します。",
                error=str(error),
            )
            return str(audio_path)

    def cleanup_temp_files(self, job_id: str, keep_final: bool = True) -> None:
        """
        ジョブの一時ファイルを削除する。
        Supabaseへのアップロード完了後に呼び出す。

        Args:
            job_id: クリーンアップ対象のジョブID
            keep_final: Trueの場合は最終MP4とサムネイルを残す
        """
        job_dir = self.media_dir / "video" / job_id
        if not job_dir.exists():
            return

        for file_path in job_dir.iterdir():
            # 最終出力ファイルは残す
            if keep_final and file_path.name in ("full.mp4", "subtitled_full.mp4", "thumbnail.jpg"):
                continue
            file_path.unlink(missing_ok=True)
            logger.debug("一時ファイルを削除", path=str(file_path))
