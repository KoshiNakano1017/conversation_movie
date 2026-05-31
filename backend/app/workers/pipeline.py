from celery import chain
from loguru import logger

from app.celery_app import celery_app


class ConversationPipeline:
    """
    コンテンツ処理の全パイプラインを管理するクラス。
    Celery chainを使って各ステップを直列実行する。
    各ステップは失敗時に自動リトライし、完了時に次ステップを起動する。

    入力ソース別の起動メソッド:
    - start_from_transcript(): テキスト貼り付け → 分析 → 動画生成 → YouTube
    - start_from_audio(): 音声ファイル → Whisper → 分析 → 動画生成 → YouTube（将来実装）
    """

    @staticmethod
    def start_from_transcript(job_id: str) -> str:
        """
        貼り付けトランスクリプトからパイプラインを開始する。
        文字起こしステップをスキップして直接Gemini分析から始める。

        Args:
            job_id: 処理対象のジョブID（transcriptionsレコードが事前に作成済みであること）

        Returns:
            Celeryタスクの非同期結果ID
        """
        from app.workers.analysis_worker import run_analysis_task
        from app.workers.video_worker import run_video_generation_task

        # .si() = immutable signature: 前タスクの戻り値を引数に注入しない
        pipeline = chain(
            run_analysis_task.si(job_id),
            run_video_generation_task.si(job_id),
        )

        result = pipeline.apply_async()
        logger.info("パイプライン開始（テキスト入力）", job_id=job_id, task_id=result.id)
        return result.id

    @staticmethod
    def start_from_audio(job_id: str) -> str:
        """
        音声ファイルからパイプラインを開始する（将来実装 - TASK-009）。
        Whisper文字起こし → 分析 → 動画生成 → YouTube の順で処理する。
        """
        from app.workers.analysis_worker import run_analysis_task
        from app.workers.transcription_worker import run_transcription_task
        from app.workers.video_worker import run_video_generation_task

        pipeline = chain(
            run_transcription_task.si(job_id),
            run_analysis_task.si(job_id),
            run_video_generation_task.si(job_id),
        )

        result = pipeline.apply_async()
        logger.info("パイプライン開始（音声ファイル）", job_id=job_id, task_id=result.id)
        return result.id
