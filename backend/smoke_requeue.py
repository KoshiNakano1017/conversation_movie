"""動作確認用: 既存ジョブを再キューイングする（前回 worker クラッシュで未処理のため）"""
import sys
sys.path.insert(0, ".")

from app.workers.pipeline import ConversationPipeline

JOB_ID = "28e176f1-ba78-4e25-a17d-afe20a9f1a06"

task_id = ConversationPipeline.start_from_transcript(JOB_ID)
print(f"Re-enqueued. task_id={task_id}")
