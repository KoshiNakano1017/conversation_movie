from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# .env はプロジェクトルート（backend/ の親）に置く
_ENV_FILE = Path(__file__).parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # App
    APP_ENV: str = "development"
    APP_SECRET_KEY: str = "change-me-in-production"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    APP_DEBUG: bool = True

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    DATABASE_URL: str = ""

    # Gemini API
    GEMINI_API_KEY: str = ""

    # YouTube
    YOUTUBE_CLIENT_ID: str = ""
    YOUTUBE_CLIENT_SECRET: str = ""
    YOUTUBE_REDIRECT_URI: str = "http://localhost:8000/api/youtube/callback"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Whisper
    WHISPER_MODEL: str = "medium"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_MODEL_DIR: str = "/app/models"

    # Storage
    MEDIA_DIR: str = "/app/media"
    MAX_UPLOAD_SIZE_MB: int = 500

    # Shotstack (動画レンダリング)
    SHOTSTACK_API_KEY: str = ""
    SHOTSTACK_ENV: str = "stage"  # "stage" | "production"

    # Remotion (廃止予定 - 後方互換のために残す)
    REMOTION_PROJECT_PATH: str = "/remotion"
    NODE_PATH: str = "/usr/bin/node"

    # FFmpeg / Remotion CLI: PATH 解決できない環境向けの明示パス（任意）
    FFMPEG_PATH: str = ""
    NPX_PATH: str = ""

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def max_upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def allowed_audio_extensions(self) -> set[str]:
        return {".mp3", ".wav", ".mp4", ".m4a", ".ogg", ".webm"}

    @property
    def allowed_audio_content_types(self) -> set[str]:
        return {
            "audio/mpeg",
            "audio/mp3",
            "audio/wav",
            "audio/x-wav",
            "video/mp4",
            "audio/mp4",
            "audio/m4a",
            "audio/x-m4a",
            "audio/ogg",
            "audio/webm",
            "video/webm",
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
