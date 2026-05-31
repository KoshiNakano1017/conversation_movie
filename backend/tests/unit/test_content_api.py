"""
content.py API エンドポイントのテスト。
GET /api/content/{job_id}/transcript
GET /api/content/{job_id}/analysis
GET /api/content/{job_id}/subtitles
"""

import uuid

from fastapi.testclient import TestClient

from app.deps import DEV_USER_ID
from app.models.analysis import Analysis
from app.models.job import Job, JobStatus
from app.models.subtitle import Subtitle
from app.models.transcription import Transcription


def _create_job(db_session, title: str = "テストジョブ") -> str:
    job_id = str(uuid.uuid4())
    db_session.add(Job(
        id=job_id,
        user_id=DEV_USER_ID,
        title=title,
        status=JobStatus.COMPLETED,
        progress=100,
        language="ja",
    ))
    db_session.commit()
    return job_id


# ─── トランスクリプトエンドポイント ──────────────────────────────


def test_get_transcript_success(client: TestClient, db_session) -> None:
    job_id = _create_job(db_session)
    db_session.add(Transcription(
        id=str(uuid.uuid4()),
        job_id=job_id,
        full_text="山田：テストの発言です。\n鈴木：はい、了解です。",
        language="ja",
        source="paste",
        segments=[],
    ))
    db_session.commit()

    response = client.get(f"/api/content/{job_id}/transcript")
    assert response.status_code == 200

    body = response.json()
    assert body["job_id"] == job_id
    assert "テストの発言" in body["full_text"]
    assert body["language"] == "ja"
    assert body["source"] == "paste"
    assert body["character_count"] > 0


def test_get_transcript_not_found(client: TestClient, db_session) -> None:
    response = client.get(f"/api/content/{uuid.uuid4()}/transcript")
    assert response.status_code == 404


def test_get_transcript_wrong_user(client: TestClient, db_session) -> None:
    """他ユーザーのジョブは取得できない"""
    job_id = str(uuid.uuid4())
    db_session.add(Job(
        id=job_id,
        user_id="other-user-id",
        title="他人のジョブ",
        status=JobStatus.COMPLETED,
        progress=100,
        language="ja",
    ))
    db_session.add(Transcription(
        id=str(uuid.uuid4()),
        job_id=job_id,
        full_text="他人のトランスクリプト",
        language="ja",
        source="paste",
        segments=[],
    ))
    db_session.commit()

    response = client.get(f"/api/content/{job_id}/transcript")
    assert response.status_code == 404


# ─── 分析結果エンドポイント ───────────────────────────────────────


def test_get_analysis_success(client: TestClient, db_session) -> None:
    job_id = _create_job(db_session, "分析結果テスト")
    db_session.add(Analysis(
        id=str(uuid.uuid4()),
        job_id=job_id,
        summary_short="短い要約です",
        summary_medium="中くらいの要約テキスト",
        summary_detailed={"overview": "詳細概要"},
        themes=["AI", "会議"],
        keywords=["キーワード1"],
        quotes=[{"speaker": "山田", "text": "名言"}],
        sentiment_timeline=[],
        overall_sentiment="positive",
        suggested_title="動画タイトル案",
        suggested_description="説明文案",
        suggested_tags=["tag1", "tag2"],
        model_name="gemini-2.5-flash",
        tokens_used=1234,
    ))
    db_session.commit()

    response = client.get(f"/api/content/{job_id}/analysis")
    assert response.status_code == 200

    body = response.json()
    assert body["job_id"] == job_id
    assert body["summary_short"] == "短い要約です"
    assert "AI" in body["themes"]
    assert body["overall_sentiment"] == "positive"
    assert body["tokens_used"] == 1234


def test_get_analysis_not_found(client: TestClient, db_session) -> None:
    response = client.get(f"/api/content/{uuid.uuid4()}/analysis")
    assert response.status_code == 404


# ─── 字幕エンドポイント ────────────────────────────────────────────


def test_get_subtitles_srt(client: TestClient, db_session) -> None:
    job_id = _create_job(db_session, "字幕テスト")
    db_session.add(Subtitle(
        id=str(uuid.uuid4()),
        job_id=job_id,
        format="srt",
        content="1\n00:00:00,000 --> 00:00:05,000\nテスト字幕\n\n",
    ))
    db_session.commit()

    response = client.get(f"/api/content/{job_id}/subtitles?format=srt")
    assert response.status_code == 200
    assert "00:00:00,000" in response.text
    assert "テスト字幕" in response.text


def test_get_subtitles_vtt(client: TestClient, db_session) -> None:
    job_id = _create_job(db_session, "VTT字幕テスト")
    db_session.add(Subtitle(
        id=str(uuid.uuid4()),
        job_id=job_id,
        format="vtt",
        content="WEBVTT\n\n00:00:00.000 --> 00:00:05.000\nVTTテスト\n\n",
    ))
    db_session.commit()

    response = client.get(f"/api/content/{job_id}/subtitles?format=vtt")
    assert response.status_code == 200
    assert "WEBVTT" in response.text


def test_get_subtitles_invalid_format(client: TestClient, db_session) -> None:
    job_id = _create_job(db_session)
    response = client.get(f"/api/content/{job_id}/subtitles?format=xml")
    assert response.status_code == 400


def test_get_subtitles_not_found(client: TestClient, db_session) -> None:
    response = client.get(f"/api/content/{uuid.uuid4()}/subtitles?format=srt")
    assert response.status_code == 404
