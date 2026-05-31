from contextlib import asynccontextmanager

import redis as redis_client
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from loguru import logger

from app.config import settings
from app.core.database import check_db_connection
from app.core.logging import setup_logging

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ANN001
    # ─── Startup ────────────────────────────────────────────────────
    logger.info("ConversationMovie APIサーバー起動", env=settings.APP_ENV)

    if settings.APP_DEBUG:
        from app.core.database import SessionLocal
        from app.models.user import User

        dev_user_id = "00000000-0000-0000-0000-000000000001"
        try:
            with SessionLocal() as db:
                exists = db.query(User).filter(User.id == dev_user_id).first()
                if not exists:
                    db.add(User(id=dev_user_id, email="dev@localhost", display_name="Dev User"))
                    db.commit()
                    logger.info("開発用devユーザーを作成しました", user_id=dev_user_id)
        except Exception as err:
            logger.warning("devユーザー作成をスキップ", error=str(err))

    yield
    # ─── Shutdown ────────────────────────────────────────────────────


app = FastAPI(
    title="ConversationMovie",
    description="Google Meet会話をAIアバター動画に自動変換するサービス",
    version="1.0.0",
    docs_url="/docs" if settings.APP_DEBUG else None,
    redoc_url="/redoc" if settings.APP_DEBUG else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.APP_DEBUG else ["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import os  # noqa: E402
from pathlib import Path as _Path  # noqa: E402

# static ディレクトリを自動作成してからマウント
_static_dir = _Path("app/static")
_static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

# 生成動画・サムネイルをローカルから配信（MVP用）
# MEDIA_DIR は .env で設定（Docker: /app/media, ローカル: ./media）
_media_dir = _Path(settings.MEDIA_DIR)
(_media_dir / "video").mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(_media_dir)), name="media")

templates = Jinja2Templates(directory="app/templates")


# ─── APIルーターの登録 ────────────────────────────────────────
from app.api import audio, auth, content, jobs, transcript, websocket, youtube  # noqa: E402

app.include_router(auth.router)
app.include_router(audio.router)
app.include_router(transcript.router)   # メインの入力エンドポイント
app.include_router(jobs.router)
app.include_router(content.router)
app.include_router(youtube.router)
app.include_router(websocket.router)


# ─── グローバル例外ハンドラ（デバッグ用） ────────────────────
import traceback  # noqa: E402

from fastapi import Request as _Request  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR  # noqa: E402


@app.exception_handler(Exception)
async def global_exception_handler(_request: _Request, exc: Exception) -> JSONResponse:
    tb = traceback.format_exc()
    logger.error("未処理例外", error=str(exc), traceback=tb)
    return JSONResponse(
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": f"{type(exc).__name__}: {exc}", "traceback": tb if settings.APP_DEBUG else None},
    )


# ─── ヘルスチェック ───────────────────────────────────────────
@app.get("/health", tags=["system"])
def health_check() -> dict:
    """
    全サービスの死活確認エンドポイント。
    CI/CDやロードバランサーの監視に使用する。
    """
    db_ok = check_db_connection()

    redis_ok = False
    try:
        r = redis_client.from_url(settings.REDIS_URL)
        r.ping()
        redis_ok = True
    except Exception as error:
        logger.warning("Redis接続エラー", error=str(error))

    all_healthy = db_ok and redis_ok

    return {
        "status": "ok" if all_healthy else "degraded",
        "version": "1.0.0",
        "services": {
            "database": "ok" if db_ok else "error",
            "redis": "ok" if redis_ok else "error",
        },
    }



# ─── HTMLページルート ────────────────────────────────────────
from fastapi import Depends, Request  # noqa: E402
from fastapi.responses import HTMLResponse  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.database import get_db  # noqa: E402


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/paste", response_class=HTMLResponse)
def paste_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("paste.html", {"request": request})


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail_page(request: Request, job_id: str) -> HTMLResponse:
    return templates.TemplateResponse("job_detail.html", {"request": request, "job_id": job_id})


@app.get("/jobs/{job_id}/preview", response_class=HTMLResponse)
def job_preview_page(
    request: Request,
    job_id: str,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    from app.models.analysis import Analysis
    from app.models.job import Job
    from app.models.video import Video

    job = db.query(Job).filter(Job.id == job_id).first()
    analysis = db.query(Analysis).filter(Analysis.job_id == job_id).first()
    video = db.query(Video).filter(Video.job_id == job_id).first()

    return templates.TemplateResponse(
        "job_preview.html",
        {"request": request, "job": job, "analysis": analysis, "video": video},
    )
