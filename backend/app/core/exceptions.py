class ConversationMovieError(Exception):
    """サービス全体のベース例外クラス"""

    def __init__(self, code: str, message: str, detail: str = "") -> None:
        self.code = code
        self.message = message
        self.detail = detail
        super().__init__(message)

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "detail": self.detail}


class AudioValidationError(ConversationMovieError):
    """音声ファイルのバリデーションエラー"""
    pass


class TranscriptionError(ConversationMovieError):
    """Whisper文字起こし処理のエラー"""
    pass


class DiarizationError(ConversationMovieError):
    """話者分離処理のエラー"""
    pass


class GeminiAnalysisError(ConversationMovieError):
    """Gemini API呼び出しのエラー"""
    pass


class VideoGenerationError(ConversationMovieError):
    """動画生成処理のエラー"""
    pass


class YouTubeError(ConversationMovieError):
    """YouTube API操作のエラー"""
    pass


class StorageError(ConversationMovieError):
    """Supabase Storage操作のエラー"""
    pass


class AuthenticationError(ConversationMovieError):
    """認証エラー"""
    pass


class NotFoundError(ConversationMovieError):
    """リソースが見つからないエラー"""
    pass
