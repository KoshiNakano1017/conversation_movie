"""
Shotstack API を使ったクラウドレンダリングサービス。

設計方針:
- Remotion / FFmpeg のローカル実行を廃止し、Shotstack REST API に委譲する
- 会議参加者の発言ターンをタイムライン化し、HTML アセットで字幕スタイルの対話表示を実現する
- TTS 音声は Supabase Storage に公開アップロードし、そのURLを Shotstack に渡す
- レンダリング結果の動画URL は Shotstack CDN から直接取得し DB に保存する

API リファレンス: https://shotstack.io/docs/api/
"""

import time
from dataclasses import dataclass, field
from typing import NamedTuple

import httpx
from loguru import logger

from app.config import settings
from app.core.exceptions import VideoGenerationError

# Shotstack が提供するベース URL
_BASE_URLS = {
    "stage": "https://api.shotstack.io/stage",
    "production": "https://api.shotstack.io/v1",
}

# 発言者ごとのアクセントカラー（サイクリック使用）
_SPEAKER_COLORS = [
    "#64b5f6",  # 青
    "#f06292",  # ピンク
    "#81c784",  # 緑
    "#ffb74d",  # オレンジ
    "#ba68c8",  # 紫
    "#4db6ac",  # ティール
    "#ff8a65",  # ディープオレンジ
    "#a1887f",  # ブラウン
]

INTRO_SECONDS = 3.0   # タイトルカード表示時間
POLL_INTERVAL = 5     # ステータス確認間隔（秒）
MAX_POLLS = 144       # 最大ポーリング回数（= 12 分）


class RenderResult(NamedTuple):
    video_url: str
    poster_url: str
    duration_seconds: float
    render_time_seconds: float
    render_id: str


@dataclass
class AudioClip:
    """Shotstack タイムラインに埋め込む音声クリップ"""
    src: str        # 公開URL
    start: float    # 秒
    length: float   # 秒


class ShotstackService:
    """Shotstack API ラッパー。タイムライン構築 → 送信 → ポーリングを担当する。"""

    def __init__(self) -> None:
        if not settings.SHOTSTACK_API_KEY:
            raise VideoGenerationError(
                code="SS001",
                message="SHOTSTACK_API_KEY が未設定です。.env を確認してください。",
            )
        env = settings.SHOTSTACK_ENV if settings.SHOTSTACK_ENV in _BASE_URLS else "stage"
        self._base_url = _BASE_URLS[env]
        self._headers = {
            "x-api-key": settings.SHOTSTACK_API_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # ──────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────

    def build_edit(
        self,
        title: str,
        speaker_turns: list[dict],
        audio_clips: list[AudioClip] | None = None,
        summary_short: str = "",
    ) -> dict:
        """
        Shotstack の edit JSON（タイムライン定義）を構築する。

        Args:
            title: 動画タイトル（タイトルカードに表示）
            speaker_turns: [{"speaker": str, "text": str, "start_seconds": float, "end_seconds": float}]
            audio_clips: TTS 音声クリップのリスト（任意）
            summary_short: 短いサマリー（タイトルカード下部に表示）

        Returns:
            Shotstack /render エンドポイントに POST する dict
        """
        audio_clips = audio_clips or []

        # 発言者 → カラーのマッピング
        speaker_list: list[str] = []
        for t in speaker_turns:
            spk = t.get("speaker", "")
            if spk and spk not in speaker_list:
                speaker_list.append(spk)
        color_map = {spk: _SPEAKER_COLORS[i % len(_SPEAKER_COLORS)] for i, spk in enumerate(speaker_list)}

        # 総秒数（最後のターン終端 + バッファ）
        total_seconds = (
            max((t.get("end_seconds", 0.0) for t in speaker_turns), default=0.0) + INTRO_SECONDS + 1.0
            if speaker_turns
            else 30.0
        )

        tracks = [
            self._build_dialogue_track(title, summary_short, speaker_turns, color_map, total_seconds),
            self._build_background_track(total_seconds),
        ]

        if audio_clips:
            tracks.insert(0, self._build_audio_track(audio_clips))

        return {
            "timeline": {
                "background": "#0d0d1a",
                "tracks": tracks,
            },
            "output": {
                "format": "mp4",
                "resolution": "hd",
                "fps": 30,
                "poster": {"capture": INTRO_SECONDS + 0.5},  # タイトルカード直後をサムネイルに
            },
        }

    def submit_render(self, edit: dict) -> str:
        """
        Shotstack にレンダリングジョブを送信し、render_id を返す。

        Raises:
            VideoGenerationError: API エラー時
        """
        with httpx.Client(timeout=30) as client:
            response = client.post(
                f"{self._base_url}/render",
                json=edit,
                headers=self._headers,
            )

        if response.status_code not in (200, 201):
            raise VideoGenerationError(
                code="SS002",
                message=f"Shotstack API エラー {response.status_code}: {response.text[:300]}",
            )

        body = response.json()
        render_id: str = body.get("response", {}).get("id", "")
        if not render_id:
            raise VideoGenerationError(
                code="SS003",
                message=f"render_id が取得できませんでした: {body}",
            )

        logger.info("Shotstack レンダリング送信完了", render_id=render_id)
        return render_id

    def poll_render(self, render_id: str) -> RenderResult:
        """
        レンダリング完了を待ち、結果を返す。

        Returns:
            RenderResult（video_url, poster_url, duration, render_time）

        Raises:
            VideoGenerationError: 失敗 / タイムアウト時
        """
        for attempt in range(MAX_POLLS):
            time.sleep(POLL_INTERVAL)

            with httpx.Client(timeout=15) as client:
                response = client.get(
                    f"{self._base_url}/render/{render_id}",
                    headers=self._headers,
                )

            if response.status_code != 200:
                raise VideoGenerationError(
                    code="SS004",
                    message=f"Shotstack ステータス取得失敗 {response.status_code}: {response.text[:200]}",
                )

            data: dict = response.json().get("response", {})
            status: str = data.get("status", "")

            logger.debug(
                "Shotstack ステータス確認",
                render_id=render_id,
                status=status,
                attempt=attempt,
            )

            if status == "done":
                video_url: str = data.get("url", "")
                if not video_url:
                    raise VideoGenerationError(
                        code="SS005",
                        message="完了したが video URL が空です",
                    )
                logger.info("Shotstack レンダリング完了", render_id=render_id, url=video_url)
                return RenderResult(
                    video_url=video_url,
                    poster_url=data.get("poster", ""),
                    duration_seconds=float(data.get("duration", 0.0)),
                    render_time_seconds=float(data.get("renderTime", 0.0)),
                    render_id=render_id,
                )

            if status in ("failed", "error"):
                error_msg: str = data.get("error", "不明なエラー")
                raise VideoGenerationError(
                    code="SS006",
                    message=f"Shotstack レンダリング失敗: {error_msg}",
                )

            # queued / fetching / rendering / saving → 次のポーリングへ

        raise VideoGenerationError(
            code="SS007",
            message=f"Shotstack タイムアウト（{MAX_POLLS * POLL_INTERVAL / 60:.0f} 分経過）: {render_id}",
        )

    # ──────────────────────────────────────────────────────────────
    # Private builders
    # ──────────────────────────────────────────────────────────────

    def _build_background_track(self, total_seconds: float) -> dict:
        """グラデーション背景クリップ（全再生時間）"""
        return {
            "clips": [
                {
                    "asset": {
                        "type": "html",
                        "html": (
                            "<html><body style='margin:0;width:1280px;height:720px;"
                            "background:linear-gradient(135deg,#0d0d1a 0%,#1a1a2e 60%,#16213e 100%);'>"
                            "</body></html>"
                        ),
                        "width": 1280,
                        "height": 720,
                    },
                    "start": 0,
                    "length": total_seconds,
                }
            ]
        }

    def _build_dialogue_track(
        self,
        title: str,
        summary_short: str,
        speaker_turns: list[dict],
        color_map: dict[str, str],
        total_seconds: float,
    ) -> dict:
        """タイトルカード + 発言ターンのオーバーレイクリップ群"""
        clips: list[dict] = []

        # ── タイトルカード ──
        subtitle_html = (
            f"<p style='color:#aaa;font-size:22px;margin-top:12px;"
            f"text-align:center;'>{summary_short[:60]}</p>"
            if summary_short
            else ""
        )
        clips.append({
            "asset": {
                "type": "html",
                "html": (
                    "<html><head>"
                    "<link href='https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap' rel='stylesheet'>"
                    "<style>*{margin:0;padding:0;box-sizing:border-box;}"
                    "body{width:1280px;height:720px;display:flex;flex-direction:column;"
                    "align-items:center;justify-content:center;"
                    "font-family:'Noto Sans JP',sans-serif;}</style></head>"
                    f"<body>"
                    f"<h1 style='color:#fff;font-size:48px;font-weight:700;"
                    f"text-align:center;line-height:1.4;padding:0 80px;'>{_esc(title)}</h1>"
                    f"{subtitle_html}"
                    f"</body></html>"
                ),
                "width": 1280,
                "height": 720,
            },
            "start": 0,
            "length": INTRO_SECONDS,
            "transition": {"in": "fade", "out": "fade"},
        })

        # ── 発言ターンごとのバブル ──
        for turn in speaker_turns:
            speaker: str = turn.get("speaker", "")
            text: str = turn.get("text", "")
            start: float = turn.get("start_seconds", 0.0) + INTRO_SECONDS
            end: float = turn.get("end_seconds", start + 3.0) + INTRO_SECONDS
            length: float = max(end - start, 1.0)
            color: str = color_map.get(speaker, "#ffffff")

            # 長すぎるテキストは省略（Shotstack HTML 描画の安定性のため）
            display_text = text if len(text) <= 120 else text[:118] + "…"

            clips.append({
                "asset": {
                    "type": "html",
                    "html": (
                        "<html><head>"
                        "<link href='https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap' rel='stylesheet'>"
                        "<style>*{margin:0;padding:0;box-sizing:border-box;}"
                        "body{width:1280px;height:720px;display:flex;flex-direction:column;"
                        "justify-content:flex-end;padding:50px;font-family:'Noto Sans JP',sans-serif;}</style></head>"
                        "<body>"
                        f"<div style='background:rgba(0,0,0,0.72);border-radius:14px;"
                        f"padding:22px 30px;max-width:960px;"
                        f"border-left:5px solid {color};'>"
                        f"<p style='color:{color};font-size:19px;font-weight:700;margin-bottom:8px;'>"
                        f"{_esc(speaker)}</p>"
                        f"<p style='color:#f0f0f0;font-size:24px;line-height:1.65;'>"
                        f"{_esc(display_text)}</p>"
                        f"</div></body></html>"
                    ),
                    "width": 1280,
                    "height": 720,
                },
                "start": start,
                "length": length,
                "transition": {"in": "fade", "out": "fade"},
            })

        return {"clips": clips}

    def _build_audio_track(self, audio_clips: list[AudioClip]) -> dict:
        """TTS 音声クリップのトラック"""
        return {
            "clips": [
                {
                    "asset": {
                        "type": "audio",
                        "src": clip.src,
                        "volume": 1.0,
                    },
                    "start": clip.start + INTRO_SECONDS,
                    "length": clip.length,
                }
                for clip in audio_clips
            ]
        }


# ─── ユーティリティ ──────────────────────────────────────────────

def _esc(text: str) -> str:
    """HTML 特殊文字をエスケープする"""
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )
