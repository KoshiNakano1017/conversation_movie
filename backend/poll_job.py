"""ジョブ状態を DB からポーリング"""
import sys
import time

sys.path.insert(0, ".")

from app.core.database import SessionLocal
from app.models.job import Job
from app.models.job_log import JobLog
from app.models.video import Video

JOB_ID = sys.argv[1] if len(sys.argv) > 1 else "cb0882e1-bccf-48c8-a1bc-872f8ea6aab3"

for i in range(120):
    with SessionLocal() as db:
        job = db.query(Job).filter(Job.id == JOB_ID).first()
        if not job:
            print("Job not found")
            break
        status = job.status.value if hasattr(job.status, "value") else job.status
        print(f"[{i}] status={status} progress={job.progress}% error={job.error_message or '-'}")
        if status in ("completed", "failed", "cancelled"):
            video = db.query(Video).filter(Video.job_id == JOB_ID).first()
            if video:
                print(f"video: {video.storage_path}")
            logs = db.query(JobLog).filter(JobLog.job_id == JOB_ID).order_by(JobLog.created_at).all()
            print("\n--- job_logs ---")
            for log in logs[-10:]:
                print(f"  [{log.level}] {log.step}: {log.message[:120]}")
            sys.exit(0 if status == "completed" else 1)
    time.sleep(5)

print("timeout")
sys.exit(1)
