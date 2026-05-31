"""
Remotion CLIとFFmpegを使った動画生成サービス。

設計方針:
- RemotionはNode.jsサブプロセスとして実行（Pythonから制御）
- FFmpegで字幕焼き込みとサムネイル抽出を実施
- 生成ファイルはローカルの /app/media/ に一時保存後、Supabase Storageへアップロード
- VideoDataのタイムスタンプ計算はPython側で行いRemotionに渡す

生成プロンプト: docs/ai-prompts/gemini_analysis.md
"""

import json
import os
import shutil
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from loguru import logger

from app.config import settings
from app.core.exceptions import VideoGenerationError

FPS = 30
INTRO_SECONDS = 3  # タイトルカード表示時間


@dataclass
class VideoData:
    """Remotionに渡す動画生成データ"""
    job_id: str
    title: str
    duration_frames: int
    fps: int
    overall_sentiment: str
    themes: list
    quotes: list
    summary_short: str
    subtitles: list
    avatar_scripts: list
    speaker_turns: list  # 会議参加者の発言ターン（会議室ビュー用）
    speakers: list       # 参加者一覧（登場順）


class VideoService:
    """
    動画生成の全工程を管理するサービス。
    1. VideoDataをJSONとして構築
    2. Remotion CLIでアバター動画をレンダリング
    3. FFmpegで字幕を焼き込み
    4. FFmpegでサムネイルを抽出
    """

    def __init__(self) -> None:
        self.media_dir = Path(settings.MEDIA_DIR)
        self.remotion_dir = Path(settings.REMOTION_PROJECT_PATH)

    # ─── 公開メソッド ──────────────────────────────────────────

    def build_video_data(
        self,
        job_id: str,
        title: str,
        analysis: dict,
        subtitles: list[dict],
        avatar_scripts: list[dict],
        speaker_turns: list[dict] | None = None,
        speakers: list[str] | None = None,
    ) -> VideoData:
        """
        DB取得データからRemotionに渡すVideoDataを組み立てる。
        アバタースクリプトの開始時刻をイントロ後から順番に計算する。

        Args:
            job_id: ジョブID
            title: 会議タイトル
            analysis: analysesテーブルのデータ
            subtitles: SubtitleSegmentのリスト
            avatar_scripts: AvatarScriptのリスト
            speaker_turns: 会議参加者の発言ターンリスト（会議室ビュー用）
            speakers: 参加者一覧（登場順）

        Returns:
            VideoData: Remotionに渡すデータ構造
        """
        turns = speaker_turns or []
        spk_list = speakers or []

        # 動画時間: speaker_turns がある場合はそちらの総時間を優先
        if turns:
            total_seconds = max(t["end_seconds"] for t in turns) + 2.0
        else:
            # アバタースクリプトに開始時刻を付与（イントロ3秒後から順番に配置）
            scripts_with_timing = self._assign_script_timings(avatar_scripts)
            if scripts_with_timing:
                last = scripts_with_timing[-1]
                total_seconds = last["start_seconds"] + last["duration_seconds"] + 2.0
            else:
                total_seconds = 30.0
            avatar_scripts = scripts_with_timing

        total_frames = int(total_seconds * FPS)

        return VideoData(
            job_id=job_id,
            title=title,
            duration_frames=total_frames,
            fps=FPS,
            overall_sentiment=analysis.get("overall_sentiment", "neutral"),
            themes=analysis.get("themes", [])[:4],
            quotes=analysis.get("quotes", [])[:3],
            summary_short=analysis.get("summary_short", ""),
            subtitles=subtitles,
            avatar_scripts=avatar_scripts if not turns else [],
            speaker_turns=turns,
            speakers=spk_list,
        )

    def render_video(self, video_data: VideoData, output_filename: str) -> Path:
        """
        Remotion CLIを呼び出して動画をレンダリングする。

        Args:
            video_data: Remotionに渡すデータ
            output_filename: 出力ファイル名（例: "full.mp4"）

        Returns:
            生成されたMP4ファイルのパス

        Raises:
            VideoGenerationError: レンダリング失敗時
        """
        job_dir = self._ensure_job_dir(video_data.job_id)
        props_path = job_dir / "video_data.json"
        output_path = job_dir / output_filename

        # VideoDataをJSONとして保存
        props_dict = asdict(video_data)
        props_path.write_text(json.dumps(props_dict, ensure_ascii=False), encoding="utf-8")
        logger.info("VideoData JSONを保存", path=str(props_path))

        start_time = time.time()
        self._run_remotion_render(props_path, output_path, video_data.duration_frames)
        elapsed = time.time() - start_time

        logger.info(
            "Remotionレンダリング完了",
            job_id=video_data.job_id,
            output=str(output_path),
            elapsed_seconds=round(elapsed, 1),
        )

        # 一時JSONを削除
        props_path.unlink(missing_ok=True)

        return output_path

    def burn_subtitles(self, video_path: Path, srt_content: str) -> Path:
        """
        FFmpegを使って字幕を動画に焼き込む。

        Args:
            video_path: 入力MP4ファイルパス
            srt_content: SRT形式の字幕テキスト

        Returns:
            字幕焼き込み済みMP4のパス
        """
        job_dir = video_path.parent
        srt_path = job_dir / "subtitles.srt"
        output_path = job_dir / f"subtitled_{video_path.name}"

        # SRTファイルを一時保存
        srt_path.write_text(srt_content, encoding="utf-8")

        # FFmpeg subtitles フィルタは Windows パスを正しく扱えないため、
        # / 区切りに変換し、ドライブレターのコロンを \: にエスケープする
        srt_filter_path = str(srt_path).replace("\\", "/").replace(":", "\\:")

        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vf", f"subtitles='{srt_filter_path}':force_style='FontName=Noto Sans JP,FontSize=20,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2,Alignment=2'",
            "-c:a", "copy",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            str(output_path),
        ]

        self._run_command(ffmpeg_cmd, step="字幕焼き込み")
        srt_path.unlink(missing_ok=True)

        logger.info("字幕焼き込み完了", output=str(output_path))
        return output_path

    def extract_thumbnail(self, video_path: Path, at_second: float = 4.0) -> Path:
        """
        FFmpegで指定時刻のフレームをJPEGとして抽出する。

        Args:
            video_path: 元動画のパス
            at_second: サムネイルを取得する時刻（秒）

        Returns:
            サムネイルJPEGのパス
        """
        output_path = video_path.parent / "thumbnail.jpg"

        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-ss", str(at_second),
            "-i", str(video_path),
            "-vframes", "1",
            "-q:v", "2",
            str(output_path),
        ]

        self._run_command(ffmpeg_cmd, step="サムネイル抽出")
        logger.info("サムネイル抽出完了", output=str(output_path))
        return output_path

    def attach_audio_track(self, video_path: Path, audio_path: Path) -> Path:
        """
        生成済み動画に外部音声トラックを合成する。
        音声がない動画（Remotion出力）に対して会議音声を付与する用途。
        """
        output_path = video_path.parent / f"with_audio_{video_path.name}"
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            str(output_path),
        ]
        self._run_command(ffmpeg_cmd, step="音声トラック合成")
        logger.info("音声トラック合成完了", output=str(output_path), audio=str(audio_path))
        return output_path

    def mix_tts_audio(
        self,
        video_path: Path,
        scripts_with_audio: list[dict],
    ) -> Path:
        """
        アバタースクリプトごとの TTS 音声を start_seconds に合わせて
        動画へ合成する。

        Args:
            video_path: 入力 MP4 ファイルパス
            scripts_with_audio: 'audio_path' と 'start_seconds' を持つスクリプトリスト

        Returns:
            音声付き MP4 のパス。有効な音声が 0 件なら入力パスをそのまま返す。
        """
        valid = [
            (s["start_seconds"], s["audio_path"])
            for s in scripts_with_audio
            if s.get("audio_path")
        ]
        if not valid:
            logger.warning("合成する TTS 音声がありません – スキップ")
            return video_path

        output_path = video_path.parent / f"tts_{video_path.name}"

        # ffmpeg の入力引数を組み立て
        inputs: list[str] = ["-i", str(video_path)]
        filter_parts: list[str] = []

        for idx, (start_sec, audio_path) in enumerate(valid):
            inputs += ["-i", str(audio_path)]
            delay_ms = int(start_sec * 1000)
            filter_parts.append(
                f"[{idx + 1}:a]adelay={delay_ms}|{delay_ms}[a{idx}]"
            )

        mix_src = "".join(f"[a{i}]" for i in range(len(valid)))
        filter_parts.append(
            f"{mix_src}amix=inputs={len(valid)}:duration=longest"
            f":dropout_transition=3:normalize=0[mixed_raw];"
            f"[mixed_raw]volume=3.0[mixed]"
        )

        filter_complex = ";".join(filter_parts)

        ffmpeg_cmd = [
            "ffmpeg", "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "0:v:0",
            "-map", "[mixed]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-ac", "2",       # ステレオ出力
            "-b:a", "192k",
            str(output_path),
        ]

        self._run_command(ffmpeg_cmd, step="TTS音声合成")
        logger.info("TTS音声合成完了", output=str(output_path), segments=len(valid))
        return output_path

    def get_video_metadata(self, video_path: Path) -> dict:
        """
        FFprobeで動画のメタデータ（時間・解像度）を取得する。

        Returns:
            dict: {duration_seconds, width, height, fps, file_size_bytes}
        """
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            str(video_path),
        ]
        try:
            resolved_cmd = self._resolve_executable(cmd)
            result = subprocess.run(resolved_cmd, capture_output=True, text=True, check=True)
            info = json.loads(result.stdout)

            video_stream = next(
                (s for s in info.get("streams", []) if s.get("codec_type") == "video"),
                {},
            )

            return {
                "duration_seconds": float(video_stream.get("duration", 0)),
                "width": int(video_stream.get("width", 0)),
                "height": int(video_stream.get("height", 0)),
                "fps": FPS,
                "file_size_bytes": video_path.stat().st_size,
            }
        except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError) as error:
            # ffprobe 実行に失敗しても、最終動画は生成済みのため処理継続する
            logger.warning("動画メタデータ取得に失敗。最小情報で継続", error=str(error))
            return {
                "duration_seconds": 0.0,
                "width": 0,
                "height": 0,
                "fps": FPS,
                "file_size_bytes": video_path.stat().st_size if video_path.exists() else 0,
            }

    # ─── 内部メソッド ──────────────────────────────────────────

    def _assign_script_timings(self, avatar_scripts: list[dict]) -> list[dict]:
        """
        アバタースクリプトにstart_secondsを付与する。
        イントロ（3秒）の後から順番に配置し、スクリプト間に0.5秒の間隔を設ける。
        """
        current_time = float(INTRO_SECONDS)
        gap_between_scripts = 0.5
        result = []

        for script in avatar_scripts:
            enriched = dict(script)
            enriched["start_seconds"] = current_time
            result.append(enriched)
            current_time += script.get("duration_seconds", 5.0) + gap_between_scripts

        return result

    def _ensure_job_dir(self, job_id: str) -> Path:
        """ジョブ専用の一時ディレクトリを作成して返す"""
        job_dir = self.media_dir / "video" / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        return job_dir

    def _run_remotion_render(
        self, props_path: Path, output_path: Path, duration_frames: int
    ) -> None:
        """Remotion CLIをサブプロセスで実行する"""
        cmd = [
            "npx", "remotion", "render",
            "--config", str(self.remotion_dir / "remotion.config.ts"),
            "MeetingVideo",
            str(output_path),
            f"--props={props_path}",
            f"--frames=0-{duration_frames - 1}",
            "--log=verbose",
        ]

        logger.info("Remotionレンダリング開始", cmd=" ".join(cmd))
        self._run_command(cmd, step="Remotionレンダリング", cwd=str(self.remotion_dir))

    def _run_command(
        self, cmd: list[str], step: str, cwd: str | None = None
    ) -> subprocess.CompletedProcess:
        """
        外部コマンドを実行し、失敗時はVideoGenerationErrorを送出する。

        Args:
            cmd: 実行するコマンドのリスト
            step: エラーメッセージ用のステップ名
            cwd: 作業ディレクトリ
        """
        resolved_cmd = self._resolve_executable(cmd)

        try:
            result = subprocess.run(
                resolved_cmd,
                capture_output=True,
                text=True,
                check=True,
                cwd=cwd,
                timeout=3600,  # 最大1時間
            )
            if result.stdout:
                logger.debug(f"[{step}] stdout", output=result.stdout[-500:])
            return result

        except subprocess.CalledProcessError as error:
            stderr_tail = (error.stderr or "")[-1500:]
            logger.error(
                f"[{step}] コマンド失敗 returncode={error.returncode}\n"
                f"cmd: {' '.join(resolved_cmd)}\n"
                f"stderr (tail):\n{stderr_tail}"
            )
            raise VideoGenerationError(
                code="VID001",
                message=f"{step}に失敗しました",
                detail=stderr_tail[-500:],
            )

        except subprocess.TimeoutExpired:
            raise VideoGenerationError(
                code="VID003",
                message=f"{step}がタイムアウトしました（1時間超過）",
            )

    # 設定値（.env の FFMPEG_PATH / NPX_PATH）から取得するフォールバックマップ
    _EXECUTABLE_FALLBACKS: dict[str, str] = {
        "ffmpeg": "FFMPEG_PATH",
        "ffprobe": "FFMPEG_PATH",   # ffprobe は ffmpeg と同じ bin にある想定
        "npx": "NPX_PATH",
    }

    def _resolve_executable(self, cmd: list[str]) -> list[str]:
        """
        コマンド配列の先頭要素を実体パスに解決する。
        Windows では PATHEXT が subprocess に効かないため shutil.which で .cmd / .exe を補う。
        PATH に見つからない場合は .env の明示パス（FFMPEG_PATH / NPX_PATH）にフォールバックする。

        Args:
            cmd: 元のコマンド配列（cmd[0] は実行ファイル名）

        Returns:
            cmd[0] を絶対パスに置き換えた新しい配列
        """
        if not cmd:
            return cmd

        executable = cmd[0]
        resolved = shutil.which(executable)

        if resolved is None:
            settings_key = self._EXECUTABLE_FALLBACKS.get(executable)
            fallback_path = getattr(settings, settings_key, "") if settings_key else ""

            # ffprobe は ffmpeg.exe と同じ bin にある（FFMPEG_PATH から導出）
            if executable == "ffprobe" and settings_key == "FFMPEG_PATH" and fallback_path:
                ffmpeg_dir = Path(fallback_path).parent
                derived = ffmpeg_dir / "ffprobe.exe"
                if derived.exists():
                    fallback_path = str(derived)

            if fallback_path and Path(fallback_path).exists():
                logger.info(
                    "実行ファイルを .env のフォールバックパスから解決",
                    executable=executable,
                    path=fallback_path,
                )
                resolved = fallback_path
            else:
                raise VideoGenerationError(
                    code="VID002",
                    message=f"実行ファイルが見つかりません: {executable}",
                    detail=(
                        f"PATH または .env の {settings_key or 'PATH'} を確認してください。"
                        f"Windows では FFmpeg / Node.js の絶対パスを .env に設定すると安定動作します。"
                    ),
                )

        return [resolved, *cmd[1:]]
