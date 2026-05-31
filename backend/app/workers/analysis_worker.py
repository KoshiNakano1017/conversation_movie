import dataclasses
import uuid

from celery import Task
from loguru import logger
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.exceptions import GeminiAnalysisError
from app.models.analysis import Analysis
from app.models.avatar_character import AvatarCharacter
from app.models.avatar_script import AvatarScript
from app.models.job import JobStatus
from app.models.subtitle import Subtitle
from app.models.transcription import Transcription
from app.services.gemini_service import (
    AvatarScriptItem,
    ConversationAnalysis,
    GeminiService,
    YouTubeMetadata,
)
from app.services.job_service import add_job_log, update_job_status
from app.services.subtitle_service import SubtitleService

DEFAULT_AVATAR_CHARACTERS = [
    {
        "name": "ハカセ",
        "description": "知識豊富でわかりやすく解説する博士キャラ",
        "personality": "知識豊富で丁寧な説明が得意。難しい内容もかみ砕いて伝える。",
        "speech_style": "落ち着いた口調で、語尾はやさしく丁寧。",
        "image_path": "/avatars/hakase/default.png",
        "color_primary": "#4ECDC4",
        "order_index": 0,
    },
    {
        "name": "ツッコミちゃん",
        "description": "元気で反応が良いリアクション担当",
        "personality": "明るくテンポが良い。意外な発見に驚いて視聴者の共感を引き出す。",
        "speech_style": "カジュアルでテンポの良い口調。",
        "image_path": "/avatars/tsukkomi/default.png",
        "color_primary": "#FF6B6B",
        "order_index": 1,
    },
    {
        "name": "まとめロボ",
        "description": "ポイント整理に強いクールなロボ",
        "personality": "論理的で整理上手。結論や次アクションを簡潔にまとめる。",
        "speech_style": "簡潔で箇条書き的、やや機械的な口調。",
        "image_path": "/avatars/matomerobo/default.png",
        "color_primary": "#95E1D3",
        "order_index": 2,
    },
]


@celery_app.task(
    name="workers.analysis",
    queue="ai",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def run_analysis_task(self: Task, job_id: str) -> dict:
    """
    Gemini APIでトランスクリプトを分析し、結果をDBに保存する。

    処理フロー:
    1. transcriptionsテーブルからテキストを取得
    2. GeminiServiceで要約・テーマ・名言・アバターセリフを一括生成
    3. analysesテーブルに分析結果を保存
    4. subtitlesテーブルにSRT/VTT字幕を保存
    5. avatar_scriptsテーブルにセリフを保存
    6. ジョブステータスをGENERATING_VIDEOに更新

    Args:
        job_id: 処理対象のジョブID（.si()で呼ばれるため前ステップの結果は受け取らない）
    """
    logger.info("AI分析タスク開始", job_id=job_id)
    update_job_status(job_id, JobStatus.ANALYZING, progress=15)

    try:
        # ── Step 1: トランスクリプトを取得 ─────────────────────
        transcript_text, language, job_title = _fetch_transcript(job_id)
        add_job_log(job_id, "analysis", f"トランスクリプト取得完了（{len(transcript_text)}文字）")

        # ── Step 2: Geminiで一括分析 ─────────────────────────
        update_job_status(job_id, JobStatus.ANALYZING, progress=25)
        gemini = GeminiService()
        analysis = gemini.analyze_conversation(transcript_text, language=language)

        logger.info(
            "Gemini分析完了",
            job_id=job_id,
            themes=analysis.themes,
            quotes_count=len(analysis.quotes),
            tokens=analysis.tokens_used,
        )
        add_job_log(
            job_id, "analysis", "Gemini分析完了",
            details={"themes": analysis.themes, "tokens_used": analysis.tokens_used},
        )

        youtube_metadata = gemini.generate_youtube_metadata(analysis)

        # ── Step 3: アバターセリフを生成 ──────────────────────
        update_job_status(job_id, JobStatus.ANALYZING, progress=45)
        avatar_scripts = gemini.generate_avatar_scripts(analysis, title=job_title)
        if not avatar_scripts:
            logger.warning("アバターセリフが0件のためフォールバック台本を生成します", job_id=job_id)
            avatar_scripts = _build_fallback_avatar_scripts(analysis)
        add_job_log(job_id, "analysis", f"アバターセリフ生成完了（{len(avatar_scripts)}件）")

        # ── Step 4: 結果をDBに保存 ────────────────────────────
        update_job_status(job_id, JobStatus.GENERATING_SUBTITLES, progress=55)
        _save_analysis(job_id, analysis, language, youtube_metadata)
        _save_subtitles(job_id, transcript_text)
        _save_avatar_scripts(job_id, avatar_scripts)

        add_job_log(job_id, "analysis", "全分析結果の保存完了")
        logger.info("AI分析タスク完了", job_id=job_id)

        return {"job_id": job_id, "status": "analysis_completed"}

    except GeminiAnalysisError as error:
        _handle_failure(self, job_id, error, step="gemini_analysis")
        raise

    except Exception as error:
        _handle_failure(self, job_id, error, step="analysis")
        raise


# ─── ヘルパー関数（ワーカー内部のみで使用） ──────────────────


def _fetch_transcript(job_id: str) -> tuple[str, str, str]:
    """
    DBからトランスクリプトと関連するジョブ情報を取得する。

    Returns:
        (transcript_text, language, job_title)
    """
    with SessionLocal() as db:
        from app.models.job import Job
        record = (
            db.query(Transcription, Job.title, Job.language)
            .join(Job, Transcription.job_id == Job.id)
            .filter(Transcription.job_id == job_id)
            .first()
        )

        if not record:
            raise ValueError(f"トランスクリプトが見つかりません: job_id={job_id}")

        transcription, job_title, language = record
        return transcription.full_text, language or "ja", job_title or ""


def _save_analysis(
    job_id: str,
    analysis: ConversationAnalysis,
    language: str,
    youtube_metadata: YouTubeMetadata,
) -> None:
    """分析結果を analyses テーブルに保存する"""
    with SessionLocal() as db:
        # 既存レコードがあれば削除して上書き
        db.query(Analysis).filter(Analysis.job_id == job_id).delete()

        record = Analysis(
            job_id=job_id,
            summary_short=analysis.summary_short,
            summary_medium=analysis.summary_medium,
            summary_detailed={
                "overview": analysis.summary_detailed.overview,
                "key_decisions": analysis.summary_detailed.key_decisions,
                "action_items": [
                    dataclasses.asdict(item)
                    for item in analysis.summary_detailed.action_items
                ],
                "next_steps": analysis.summary_detailed.next_steps,
            },
            themes=analysis.themes,
            keywords=analysis.keywords,
            quotes=[dataclasses.asdict(q) for q in analysis.quotes],
            overall_sentiment=analysis.overall_sentiment,
            suggested_title=youtube_metadata.title,
            suggested_description=youtube_metadata.description,
            suggested_tags=youtube_metadata.tags,
            model_name=GeminiService.GEMINI_MODEL,
            tokens_used=analysis.tokens_used,
        )
        db.add(record)
        db.commit()


def _save_subtitles(job_id: str, transcript_text: str) -> None:
    """SRT・VTT形式の字幕を subtitles テーブルに保存する"""
    svc = SubtitleService()
    srt_content = svc.generate_srt(transcript_text)
    vtt_content = svc.generate_vtt(transcript_text)

    with SessionLocal() as db:
        db.query(Subtitle).filter(Subtitle.job_id == job_id).delete()

        for fmt, content in [("srt", srt_content), ("vtt", vtt_content)]:
            db.add(Subtitle(job_id=job_id, format=fmt, content=content))

        db.commit()


def _save_avatar_scripts(job_id: str, scripts: list) -> None:
    """アバターセリフを avatar_scripts テーブルに保存する"""
    with SessionLocal() as db:
        db.query(AvatarScript).filter(AvatarScript.job_id == job_id).delete()

        # キャラクター名からIDを引くマップを構築
        characters = db.query(AvatarCharacter).filter(AvatarCharacter.is_active == True).all()  # noqa: E712
        if not characters:
            logger.warning("avatar_characters が空のためデフォルトキャラを自動作成します")
            for char in DEFAULT_AVATAR_CHARACTERS:
                db.add(
                    AvatarCharacter(
                        id=str(uuid.uuid4()),
                        name=char["name"],
                        description=char["description"],
                        personality=char["personality"],
                        speech_style=char["speech_style"],
                        image_path=char["image_path"],
                        color_primary=char["color_primary"],
                        order_index=char["order_index"],
                        is_active=True,
                    )
                )
            db.commit()
            characters = db.query(AvatarCharacter).filter(AvatarCharacter.is_active == True).all()  # noqa: E712

        name_to_id = {c.name: c.id for c in characters}

        for order_index, script in enumerate(scripts):
            character_id = name_to_id.get(script.character_name)
            if not character_id:
                logger.warning("キャラクターIDが見つかりません", name=script.character_name)
                continue

            db.add(AvatarScript(
                job_id=job_id,
                character_id=character_id,
                script_text=script.script_text,
                duration_seconds=len(script.script_text) * 0.18,
                section=script.section,
                order_index=order_index,
            ))

        db.commit()


def _build_fallback_avatar_scripts(analysis: ConversationAnalysis) -> list[AvatarScriptItem]:
    """
    Geminiのセリフ生成が失敗した場合の最小フォールバック台本を返す。
    アバターを必ず表示できるよう、3キャラ分を固定で作る。
    """
    intro = analysis.summary_short or "今回の会議内容を分かりやすく解説します。"
    quote_text = analysis.quotes[0].text if analysis.quotes else "特に重要な発言をピックアップして紹介します。"
    outro = "ポイントを整理すると、重要テーマの優先順位を明確にできました。"

    return [
        AvatarScriptItem(
            character_name="ハカセ",
            section="intro",
            script_text=f"なるほど、これは興味深い会議でした。{intro}",
            target_chars=150,
        ),
        AvatarScriptItem(
            character_name="ツッコミちゃん",
            section="quote",
            script_text=f"えっ、ここがすごいポイントだね！「{quote_text}」",
            target_chars=120,
        ),
        AvatarScriptItem(
            character_name="まとめロボ",
            section="outro",
            script_text=f"ポイントを整理します。{outro}",
            target_chars=100,
        ),
    ]


def _handle_failure(task: Task, job_id: str, error: Exception, step: str) -> None:
    """タスク失敗時の共通処理"""
    logger.error(f"AI分析タスク失敗 [{step}]", job_id=job_id, error=str(error))
    add_job_log(job_id, step, str(error), level="error")
    update_job_status(
        job_id,
        JobStatus.FAILED,
        error_message=f"[{step}] {str(error)}",
    )
