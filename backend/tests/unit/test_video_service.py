"""
VideoService のユニットテスト。
subprocess を使わない純粋なロジック（build_video_data, _assign_script_timings）を対象とする。
"""

import pytest

from app.services.video_service import FPS, INTRO_SECONDS, VideoService


@pytest.fixture
def service(tmp_path):
    svc = VideoService()
    svc.media_dir = tmp_path
    return svc


# ─── _assign_script_timings テスト ─────────────────────────────────


def test_assign_script_timings_starts_after_intro(service: VideoService) -> None:
    """最初のスクリプトはイントロ秒数後から始まる"""
    scripts = [
        {"script_text": "あいさつです。", "duration_seconds": 5.0, "order_index": 0},
    ]
    result = service._assign_script_timings(scripts)
    assert result[0]["start_seconds"] == float(INTRO_SECONDS)


def test_assign_script_timings_sequential(service: VideoService) -> None:
    """スクリプトが順番に（間隔0.5秒で）配置される"""
    scripts = [
        {"script_text": "一つ目", "duration_seconds": 4.0, "order_index": 0},
        {"script_text": "二つ目", "duration_seconds": 3.0, "order_index": 1},
    ]
    result = service._assign_script_timings(scripts)
    # 2つ目は 1つ目の start + duration + gap(0.5秒) から始まる
    expected_start_2 = float(INTRO_SECONDS) + 4.0 + 0.5
    assert result[1]["start_seconds"] == pytest.approx(expected_start_2)


def test_assign_script_timings_empty_input(service: VideoService) -> None:
    """空リストは空リストを返す"""
    result = service._assign_script_timings([])
    assert result == []


def test_assign_script_timings_preserves_all_fields(service: VideoService) -> None:
    """元のフィールドがそのまま保持される"""
    scripts = [
        {
            "script_text": "テスト",
            "duration_seconds": 5.0,
            "order_index": 0,
            "character_name": "ハカセ",
            "section": "intro",
        },
    ]
    result = service._assign_script_timings(scripts)
    assert result[0]["character_name"] == "ハカセ"
    assert result[0]["section"] == "intro"
    assert "start_seconds" in result[0]


# ─── build_video_data テスト ──────────────────────────────────────


def test_build_video_data_basic(service: VideoService) -> None:
    analysis = {
        "overall_sentiment": "positive",
        "themes": ["AI", "会議", "生産性", "自動化", "効率化"],
        "quotes": [
            {"speaker": "山田", "text": "名言1", "reason": ""},
            {"speaker": "鈴木", "text": "名言2", "reason": ""},
            {"speaker": "田中", "text": "名言3", "reason": ""},
            {"speaker": "佐藤", "text": "名言4", "reason": ""},
        ],
        "summary_short": "会議の要約テキストです",
    }
    scripts = [
        {"script_text": "セリフ1", "duration_seconds": 5.0, "order_index": 0},
        {"script_text": "セリフ2", "duration_seconds": 4.0, "order_index": 1},
    ]

    result = service.build_video_data(
        job_id="test-job-001",
        title="テスト会議",
        analysis=analysis,
        subtitles=[],
        avatar_scripts=scripts,
    )

    assert result.job_id == "test-job-001"
    assert result.title == "テスト会議"
    assert result.fps == FPS
    assert result.overall_sentiment == "positive"
    assert len(result.themes) <= 4       # 上位4テーマに絞られる
    assert len(result.quotes) <= 3       # 上位3名言に絞られる
    assert result.summary_short == "会議の要約テキストです"
    assert result.duration_frames > 0


def test_build_video_data_uses_fallback_duration_when_no_scripts(
    service: VideoService,
) -> None:
    """スクリプトが空の場合は30秒のデフォルト動画長を使う"""
    result = service.build_video_data(
        job_id="empty-scripts",
        title="スクリプトなし",
        analysis={"overall_sentiment": "neutral", "themes": [], "quotes": [], "summary_short": ""},
        subtitles=[],
        avatar_scripts=[],
    )
    assert result.duration_frames == int(30.0 * FPS)


def test_build_video_data_limits_themes_to_4(service: VideoService) -> None:
    """テーマは最大4件に絞られる"""
    many_themes = [f"テーマ{i}" for i in range(10)]
    result = service.build_video_data(
        job_id="theme-test",
        title="テーマ多数",
        analysis={
            "overall_sentiment": "neutral",
            "themes": many_themes,
            "quotes": [],
            "summary_short": "",
        },
        subtitles=[],
        avatar_scripts=[],
    )
    assert len(result.themes) == 4


# ─── _ensure_job_dir テスト ───────────────────────────────────────


def test_ensure_job_dir_creates_directory(service: VideoService, tmp_path) -> None:
    job_id = "dir-test-job"
    job_dir = service._ensure_job_dir(job_id)
    assert job_dir.exists()
    assert job_dir == tmp_path / "video" / job_id
