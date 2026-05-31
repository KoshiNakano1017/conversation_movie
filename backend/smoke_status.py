"""動作確認用: 投入したジョブの DB 上の状態を確認する"""
import sys
sys.path.insert(0, ".")

from app.core.database import SessionLocal
from app.models.job import Job, JobStatus
from app.models.job_log import JobLog

JOB_ID = "28e176f1-ba78-4e25-a17d-afe20a9f1a06"

with SessionLocal() as db:
    job = db.query(Job).filter(Job.id == JOB_ID).first()
    if not job:
        print("Job not found")
    else:
        print(f"id: {job.id}")
        print(f"title: {job.title}")
        print(f"status: {job.status}")
        print(f"progress: {job.progress}")
        print(f"celery_task_id: {job.celery_task_id}")
        print(f"error_message: {job.error_message}")
        print(f"created_at: {job.created_at}")
        print(f"updated_at: {job.updated_at}")

    print("\n--- job_logs ---")
    logs = db.query(JobLog).filter(JobLog.job_id == JOB_ID).order_by(JobLog.created_at).all()
    for log in logs:
        print(f"[{log.created_at}] [{log.level}] {log.step}: {log.message}")
