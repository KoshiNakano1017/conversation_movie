import ssl

from celery import Celery

from app.config import settings

# Upstash など rediss:// を使う場合は SSL 証明書検証を無効化
_redis_ssl_opts = {}
if settings.REDIS_URL.startswith("rediss://"):
    _redis_ssl_opts = {
        "broker_use_ssl": {"ssl_cert_reqs": ssl.CERT_NONE},
        "redis_backend_use_ssl": {"ssl_cert_reqs": ssl.CERT_NONE},
    }

celery_app = Celery(
    "conversation_movie",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.workers.transcription_worker",
        "app.workers.diarization_worker",
        "app.workers.analysis_worker",
        "app.workers.video_worker",
        "app.workers.youtube_worker",
    ],
)

celery_app.conf.update(
    **_redis_ssl_opts,
    # タスクのシリアライズ形式
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Tokyo",
    enable_utc=True,

    # タスクキューの定義
    task_queues={
        "ai": {"exchange": "ai", "routing_key": "ai"},
        "video": {"exchange": "video", "routing_key": "video"},
        "upload": {"exchange": "upload", "routing_key": "upload"},
    },
    task_default_queue="ai",

    # リトライ設定
    task_max_retries=3,
    task_default_retry_delay=30,

    # タイムアウト設定
    task_soft_time_limit=3600,   # 1時間でソフトタイムアウト
    task_time_limit=7200,        # 2時間でハードタイムアウト

    # ワーカー設定
    worker_prefetch_multiplier=1,   # 1タスクずつ取得（大きなタスク向け）
    worker_max_tasks_per_child=10,  # 10タスクごとにワーカーを再起動（メモリリーク対策）

    # 結果の保持期間
    result_expires=86400,  # 24時間
)
