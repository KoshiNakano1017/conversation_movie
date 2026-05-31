from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.deps import get_current_user_id, get_db_session
from app.models.analysis import Analysis
from app.models.job import Job
from app.models.subtitle import Subtitle
from app.models.transcription import Transcription

router = APIRouter(prefix="/api/content", tags=["content"])


@router.get("/{job_id}/transcript")
def get_transcript(
    job_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
) -> dict:
    """ジョブのトランスクリプト本文を返す"""
    record = (
        db.query(Transcription)
        .join(Job, Transcription.job_id == Job.id)
        .filter(Transcription.job_id == job_id, Job.user_id == user_id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="トランスクリプトが見つかりません")

    return {
        "job_id": job_id,
        "full_text": record.full_text,
        "language": record.language,
        "source": record.source,
        "character_count": len(record.full_text),
    }


@router.get("/{job_id}/analysis")
def get_analysis(
    job_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
) -> dict:
    """ジョブのAI分析結果を返す"""
    record = (
        db.query(Analysis)
        .join(Job, Analysis.job_id == Job.id)
        .filter(Analysis.job_id == job_id, Job.user_id == user_id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="分析結果がまだ生成されていません")

    return {
        "job_id": job_id,
        "summary_short": record.summary_short,
        "summary_medium": record.summary_medium,
        "summary_detailed": record.summary_detailed,
        "themes": record.themes,
        "keywords": record.keywords,
        "quotes": record.quotes,
        "overall_sentiment": record.overall_sentiment,
        "suggested_title": record.suggested_title,
        "suggested_description": record.suggested_description,
        "suggested_tags": record.suggested_tags,
        "model_name": record.model_name,
        "tokens_used": record.tokens_used,
    }


@router.get("/{job_id}/subtitles", response_class=PlainTextResponse)
def get_subtitles(
    job_id: str,
    format: str = "srt",
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
) -> str:
    """字幕ファイルをテキストで返す（format: srt / vtt）"""
    if format not in ("srt", "vtt"):
        raise HTTPException(status_code=400, detail="format は 'srt' または 'vtt' を指定してください")

    record = (
        db.query(Subtitle)
        .join(Job, Subtitle.job_id == Job.id)
        .filter(Subtitle.job_id == job_id, Subtitle.format == format, Job.user_id == user_id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="字幕がまだ生成されていません")

    return record.content
