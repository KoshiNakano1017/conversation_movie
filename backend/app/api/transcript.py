import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.deps import get_current_user_id, get_db_session
from app.models.job import Job, JobStatus
from app.models.transcription import Transcription
from app.workers.pipeline import ConversationPipeline

router = APIRouter(prefix="/api/transcript", tags=["transcript"])

# ─── リクエスト / レスポンス スキーマ ──────────────────────────


class TranscriptPasteRequest(BaseModel):
    """トランスクリプト貼り付けリクエスト"""

    title: str = Field(..., min_length=1, max_length=100, description="タイトル")
    text: str = Field(..., min_length=10, description="貼り付ける本文（会議録/ニュース/スレッド/一般テキスト）")
    language: str = Field(default="ja", description="言語コード (ja / en)")
    description: str | None = Field(default=None, description="説明（任意）")
    content_type: str = Field(
        default="meeting",
        description="入力種別: meeting（会議録）/ news（ニュース記事）/ thread（掲示板スレッド）/ auto（自動判定）",
    )


class TranscriptPasteResponse(BaseModel):
    """トランスクリプト貼り付けレスポンス"""

    job_id: str
    status: str
    character_count: int
    websocket_url: str


# ─── エンドポイント ───────────────────────────────────────────


@router.post("/paste", response_model=TranscriptPasteResponse, status_code=202)
def paste_transcript(
    request: TranscriptPasteRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
) -> TranscriptPasteResponse:
    """
    トランスクリプトテキストを貼り付けてAI分析パイプラインを開始する。

    音声ファイルのアップロード・Whisper処理をスキップし、
    入力テキストを直接Gemini分析に渡す。
    """
    raw_text = request.text.strip()
    if len(raw_text) < 10:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="テキストが短すぎます（10文字以上必要です）",
        )

    allowed_types = {"meeting", "news", "thread", "auto"}
    content_type = request.content_type if request.content_type in allowed_types else "meeting"

    # ─── 会議録以外は会話台本に変換 ───────────────────────────
    transcript_text = raw_text
    if content_type != "meeting":
        try:
            from app.services.gemini_service import GeminiService

            gemini = GeminiService()
            transcript_text = gemini.adapt_to_dialogue(
                raw_text, content_type=content_type, language=request.language
            )
            logger.info(
                "コンテンツを会話台本に変換",
                content_type=content_type,
                original_chars=len(raw_text),
                adapted_chars=len(transcript_text),
            )
        except Exception as error:
            logger.warning(
                "会話台本への変換に失敗。元テキストで継続",
                content_type=content_type,
                error=str(error),
            )
            transcript_text = raw_text

    character_count = len(transcript_text)
    job_id = str(uuid.uuid4())

    # ─── ジョブレコードを作成 ──────────────────────────────
    job = Job(
        id=job_id,
        user_id=user_id,
        title=request.title,
        description=request.description,
        status=JobStatus.ANALYZING,
        progress=10,
        language=request.language,
    )
    db.add(job)

    # ─── トランスクリプトレコードを作成 ───────────────────
    transcription = Transcription(
        job_id=job_id,
        full_text=transcript_text,
        language=request.language,
        source=f"paste:{content_type}",
        segments=[],
    )
    db.add(transcription)
    db.commit()

    logger.info(
        "トランスクリプト受付完了",
        job_id=job_id,
        title=request.title,
        content_type=content_type,
        characters=character_count,
    )

    # ─── パイプラインを分析ステップから開始 ────────────────
    task_id = ConversationPipeline.start_from_transcript(job_id)

    # Celeryタスクのトラッキングも記録
    db.query(Job).filter(Job.id == job_id).update({"celery_task_id": task_id})
    db.commit()

    return TranscriptPasteResponse(
        job_id=job_id,
        status="analyzing",
        character_count=character_count,
        websocket_url=f"/ws/jobs/{job_id}",
    )


@router.get("/{job_id}")
def get_transcript(
    job_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
) -> dict:
    """ジョブに紐づくトランスクリプト本文を返す"""
    transcript = (
        db.query(Transcription)
        .join(Job, Transcription.job_id == Job.id)
        .filter(Transcription.job_id == job_id, Job.user_id == user_id)
        .first()
    )

    if not transcript:
        raise HTTPException(status_code=404, detail="トランスクリプトが見つかりません")

    return {
        "job_id": job_id,
        "full_text": transcript.full_text,
        "language": transcript.language,
        "source": transcript.source,
        "character_count": len(transcript.full_text),
        "created_at": transcript.created_at.isoformat(),
    }
