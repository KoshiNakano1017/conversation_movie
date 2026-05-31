"""
Whisper を使った文字起こしサービス。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config import settings
from app.core.exceptions import TranscriptionError


class TranscriptionService:
    """音声ファイルを文字起こしして構造化結果を返す。"""

    def __init__(self) -> None:
        self.model_name = settings.WHISPER_MODEL
        self.device = settings.WHISPER_DEVICE
        self.model_dir = settings.WHISPER_MODEL_DIR
        self._model: Any | None = None

    def transcribe_audio_file(self, audio_path: str, language: str | None = None) -> dict[str, Any]:
        """
        Whisper で音声を文字起こしする。

        Returns:
            {
              "text": str,
              "language": str,
              "segments": list[dict],
            }
        """
        path = Path(audio_path)
        if not path.exists():
            raise TranscriptionError(
                code="TRN001",
                message=f"音声ファイルが見つかりません: {audio_path}",
            )

        model = self._get_model()
        language_arg = language if language and language not in {"auto", "und"} else None

        try:
            result = model.transcribe(
                str(path),
                language=language_arg,
                verbose=False,
                fp16=self.device.startswith("cuda"),
            )
        except Exception as error:
            raise TranscriptionError(
                code="TRN002",
                message="Whisperによる文字起こしに失敗しました",
                detail=str(error),
            ) from error

        text = str(result.get("text", "")).strip()
        detected_language = str(result.get("language") or language or "ja")
        raw_segments = result.get("segments") or []

        segments = [
            {
                "id": int(seg.get("id", idx)),
                "start": float(seg.get("start", 0.0)),
                "end": float(seg.get("end", 0.0)),
                "text": str(seg.get("text", "")).strip(),
                "speaker": "",
            }
            for idx, seg in enumerate(raw_segments)
        ]

        if not text:
            raise TranscriptionError(
                code="TRN003",
                message="文字起こし結果が空でした",
            )

        return {"text": text, "language": detected_language, "segments": segments}

    def _get_model(self) -> Any:
        if self._model is not None:
            return self._model

        try:
            import whisper  # type: ignore[import-not-found]
        except Exception as error:
            raise TranscriptionError(
                code="TRN004",
                message="Whisperがインストールされていません（requirements-whisper.txt を導入してください）",
                detail=str(error),
            ) from error

        try:
            self._model = whisper.load_model(
                self.model_name,
                device=self.device,
                download_root=self.model_dir,
            )
            return self._model
        except Exception as error:
            raise TranscriptionError(
                code="TRN005",
                message="Whisperモデルのロードに失敗しました",
                detail=str(error),
            ) from error
