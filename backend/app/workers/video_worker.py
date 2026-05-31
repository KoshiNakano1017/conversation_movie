"""
Celery タスク: Shotstack を使ったクラウド動画レンダリング。

処理フロー:
1. DB から analysis / speaker_turns を取得
2. TTS 音声を生成（edge-tts が使える場合）
3. TTS 音声を Supabase Storage に公開アップロード（Shotstack が HTTP フェッチするため）
4. ShotstackService でタイムライン JSON を構築
5. Shotstack API にレンダリングを送信（非同期）
6. ポーリングで完了を待ち、動画 URL を取得
7. videos テーブルに記録してジョブを COMPLETED に更新
"""

import uuid
from pathlib import Path

from celery import Task
from loguru import logger

from app.celery_app import celery_app
from app.config import settings
from app.core.database import SessionLocal
from app.core.exceptions import VideoGenerationError
from app.models.analysis import Analysis
from app.models.audio_file import AudioFile
from app.models.job import Job, JobStatus
from app.models.subtitle import Subtitle
from app.models.transcription import Transcription
from app.models.video import Video, VideoType
from app.services.job_service import add_job_log, update_job_status
from app.services.shotstack_service import AudioClip, ShotstackService
from app.services.storage_service import StorageService
from app.services.subtitle_service import SubtitleService
from app.services.tts_service import TTSService


@celery_app.task(
    name="workers.video_generation",
    queue="video",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def run_video_generation_task(self: Task, job_id: str) -> dict:
    """
    Shotstack でクラウドレンダリングして動画 URL を DB に記録するタスク。

    Args:
        job_id: 処理対象のジョブID（.si() で呼ばれるため前ステップの結果は受け取らない）
    """
    logger.info("動画生成タスク開始（Shotstack）", job_id=job_id)
    update_job_status(job_id, JobStatus.GENERATING_VIDEO, progress=65)

    try:
        # ── Step 1: 必要なデータを DB から取得 ──────────────────
        job_title, user_id, analysis_data, speaker_turns, speakers = _fetch_required_data(job_id)
        add_job_log(job_id, "video", "動画生成データ取得完了")
        update_job_status(job_id, JobStatus.GENERATING_VIDEO, progress=68)

        # ── Step 2: TTS 音声を生成（任意） ─────────────────────
        audio_clips: list[AudioClip] = []
        tts_svc = TTSService()
        storage_svc = StorageService()

        if tts_svc.is_available() and speaker_turns:
            try:
                add_job_log(job_id, "video", "TTS 音声生成開始")
                job_dir = Path(settings.MEDIA_DIR) / "audio" / job_id
                job_dir.mkdir(parents=True, exist_ok=True)

                turns_with_audio = tts_svc.generate_for_speaker_turns(
                    speaker_turns, speakers, job_dir
                )

                # ── Step 3: Supabase Storage に公開アップロード ──
                for turn in turns_with_audio:
                    audio_path_str: str = turn.get("audio_path", "")
                    if not audio_path_str:
                        continue
                    audio_path = Path(audio_path_str)
                    if not audio_path.exists():
                        continue

                    public_url = storage_svc.upload_audio_public(job_id, audio_path)

                    start = float(turn.get("start_seconds", 0.0))
                    end = float(turn.get("end_seconds", start + 3.0))
                    length = max(end - start, 0.5)

                    # Supabase 未設定の場合 upload_audio_public はローカルパスを返す
                    # → その場合 Shotstack はアクセスできないため TTS をスキップ
                    if public_url.startswith("http"):
                        audio_clips.append(AudioClip(src=public_url, start=start, length=length))

                add_job_log(job_id, "video", f"TTS 音声生成完了（{len(audio_clips)} クリップ）")

            except Exception as tts_error:
                logger.warning("TTS 生成失敗。無音動画で続行します", job_id=job_id, error=str(tts_error))
                add_job_log(job_id, "video", f"TTS をスキップ: {tts_error}", level="warning")
                audio_clips = []

        update_job_status(job_id, JobStatus.GENERATING_VIDEO, progress=72)

        # ── Step 4: Shotstack タイムライン JSON を構築 ──────────
        ss_svc = ShotstackService()
        edit = ss_svc.build_edit(
            title=job_title,
            speaker_turns=speaker_turns,
            audio_clips=audio_clips if audio_clips else None,
            summary_short=analysis_data.get("summary_short", ""),
        )
        add_job_log(job_id, "video", "Shotstack タイムライン構築完了")
        update_job_status(job_id, JobStatus.GENERATING_VIDEO, progress=75)

        # ── Step 5: Shotstack API にレンダリング送信 ────────────
        add_job_log(job_id, "video", "Shotstack レンダリング送信")
        render_id = ss_svc.submit_render(edit)
        add_job_log(job_id, "video", f"Shotstack render_id: {render_id}")
        update_job_status(job_id, JobStatus.GENERATING_VIDEO, progress=78)

        # ── Step 6: ポーリングで完了を待つ ─────────────────────
        add_job_log(job_id, "video", "Shotstack レンダリング完了待ち（最大 12 分）")
        result = ss_svc.poll_render(render_id)
        add_job_log(
            job_id,
            "video",
            f"Shotstack レンダリング完了（{result.render_time_seconds:.1f} 秒）",
            details={"video_url": result.video_url, "duration": result.duration_seconds},
        )
        update_job_status(job_id, JobStatus.GENERATING_VIDEO, progress=95)

        # ── Step 7: DB に記録してジョブ完了 ─────────────────────
        _save_video_record(
            job_id=job_id,
            user_id=user_id,
            storage_path=result.video_url,
            thumbnail_path=result.poster_url,
            duration_seconds=result.duration_seconds,
            render_time_seconds=result.render_time_seconds,
            render_id=render_id,
        )

        update_job_status(job_id, JobStatus.COMPLETED, progress=100)
        add_job_log(
            job_id,
            "video",
            "動画生成完了",
            details={
                "duration_seconds": result.duration_seconds,
                "video_url": result.video_url,
            },
        )

        logger.info("動画生成タスク完了", job_id=job_id, video_url=result.video_url)
        return {"job_id": job_id, "status": "video_completed", "video_url": result.video_url}

    except VideoGenerationError as error:
        _handle_failure(self, job_id, error, step="video_generation")
        raise

    except Exception as error:
        _handle_failure(self, job_id, error, step="video_unexpected")
        raise


# ─── ヘルパー関数 ──────────────────────────────────────────────


def _fetch_required_data(
    job_id: str,
) -> tuple[str, str, dict, list[dict], list[str]]:
    """
    動画生成に必要なデータを DB から一括取得する。

    Returns:
        (job_title, user_id, analysis_dict, speaker_turns, speakers)
    """
    with SessionLocal() as db:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise ValueError(f"ジョブが見つかりません: {job_id}")

        analysis = db.query(Analysis).filter(Analysis.job_id == job_id).first()
        if not analysis:
            raise ValueError(f"分析結果が見つかりません: {job_id}")

        analysis_dict = {
            "overall_sentiment": analysis.overall_sentiment or "neutral",
            "themes": analysis.themes or [],
            "quotes": analysis.quotes or [],
            "summary_short": analysis.summary_short or "",
        }

        # トランスクリプトから speaker_turns を生成（タイミング情報付き）
        transcription = db.query(Transcription).filter(Transcription.job_id == job_id).first()
        speaker_turns: list[dict] = []
        speakers: list[str] = []
        if transcription and transcription.full_text:
            svc = SubtitleService()
            turns = svc.extract_speaker_turns(transcription.full_text)
            speaker_turns = [
                {
                    "speaker": t.speaker,
                    "text": t.text,
                    "start_seconds": t.start_seconds,
                    "end_seconds": t.end_seconds,
                }
                for t in turns
            ]
            speakers = svc.unique_speakers(transcription.full_text)

        return job.title, job.user_id, analysis_dict, speaker_turns, speakers


def _save_video_record(
    job_id: str,
    user_id: str,
    storage_path: str,
    thumbnail_path: str,
    duration_seconds: float,
    render_time_seconds: float,
    render_id: str,
) -> None:
    """動画ファイル情報を videos テーブルに保存する"""
    with SessionLocal() as db:
        db.query(Video).filter(Video.job_id == job_id).delete()

        video = Video(
            id=str(uuid.uuid4()),
            job_id=job_id,
            user_id=user_id,
            video_type=VideoType.FULL,
            storage_path=storage_path,
            storage_bucket="shotstack",
            duration_seconds=duration_seconds if duration_seconds > 0 else None,
            render_time_seconds=render_time_seconds if render_time_seconds > 0 else None,
            thumbnail_path=thumbnail_path or None,
            render_backend="shotstack",
            shotstack_render_id=render_id,
        )
        db.add(video)
        db.commit()


def _handle_failure(task: Task, job_id: str, error: Exception, step: str) -> None:
    """タスク失敗時の共通エラー処理"""
    logger.error(f"動画生成タスク失敗 [{step}]", job_id=job_id, error=str(error))
    add_job_log(job_id, step, str(error), level="error")
    update_job_status(
        job_id,
        JobStatus.FAILED,
        error_message=f"[{step}] {str(error)}",
    )
