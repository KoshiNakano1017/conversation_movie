"""
SRT / WebVTT 字幕ファイルの生成サービス。

テキスト貼り付け入力の場合、タイムスタンプは存在しない。
そのため、文字数ベースで均等に時間を割り当てる方式を採用する。

設計方針:
- 話者名「山田：」の形式を自動検出して字幕に含める
- 1字幕ブロックは最大40文字（可読性のため）
- タイムスタンプがない場合は話者の発言量から推定
"""

import re
from dataclasses import dataclass


@dataclass
class SubtitleSegment:
    """字幕の1ブロック"""
    index: int
    start_seconds: float
    end_seconds: float
    speaker: str      # 空文字の場合は話者不明
    text: str


@dataclass
class SpeakerTurn:
    """1人の発言ターン（会議室ビュー用）"""
    speaker: str
    text: str
    start_seconds: float
    end_seconds: float


class SubtitleService:
    """トランスクリプトから字幕ファイルを生成するサービス"""

    # 1文字あたりの推定読み上げ時間（秒）
    SECONDS_PER_CHAR = 0.18

    # 字幕1ブロックの最大文字数
    MAX_CHARS_PER_BLOCK = 40

    # 話者ラベルを検出する正規表現（「山田：」「A:」などに対応）
    SPEAKER_PATTERN = re.compile(r"^([^\s：:]{1,20})[：:]\s*")

    def extract_speaker_turns(self, transcript: str) -> list[SpeakerTurn]:
        """
        トランスクリプトから発言ターンリストを生成する（会議室ビュー用）。
        1ターン = 1話者の連続した発言。タイムスタンプは文字数から推定。

        Returns:
            SpeakerTurn リスト（start_seconds / end_seconds 付き）
        """
        lines = [l.strip() for l in transcript.splitlines() if l.strip()]
        turns: list[SpeakerTurn] = []
        current_time = 0.0
        PAUSE_BETWEEN = 0.4  # 発言間の間隔（秒）

        for line in lines:
            speaker, text = self._extract_speaker(line)
            if not text:
                continue
            duration = max(2.0, len(text) * self.SECONDS_PER_CHAR)
            turns.append(SpeakerTurn(
                speaker=speaker or "不明",
                text=text,
                start_seconds=current_time,
                end_seconds=current_time + duration,
            ))
            current_time += duration + PAUSE_BETWEEN

        return turns

    def unique_speakers(self, transcript: str) -> list[str]:
        """トランスクリプトから話者リスト（登場順・重複なし）を返す"""
        seen: list[str] = []
        for line in transcript.splitlines():
            speaker, _ = self._extract_speaker(line.strip())
            if speaker and speaker not in seen:
                seen.append(speaker)
        return seen

    # ─── 公開メソッド ─────────────────────────────────────────

    def generate_srt(self, transcript: str) -> str:
        """
        トランスクリプトからSRT形式の字幕文字列を生成する。

        Args:
            transcript: トランスクリプト本文（改行区切りの発言）

        Returns:
            SRT形式の文字列
        """
        segments = self._build_segments(transcript)
        return self._segments_to_srt(segments)

    def generate_vtt(self, transcript: str) -> str:
        """
        トランスクリプトからWebVTT形式の字幕文字列を生成する。
        """
        segments = self._build_segments(transcript)
        return self._segments_to_vtt(segments)

    # ─── 内部処理 ─────────────────────────────────────────────

    def _build_segments(self, transcript: str) -> list[SubtitleSegment]:
        """
        トランスクリプト本文を解析して SubtitleSegment リストを構築する。
        各発言を最大文字数で分割し、文字数から推定タイムスタンプを付与する。
        """
        lines = [line.strip() for line in transcript.splitlines() if line.strip()]
        segments: list[SubtitleSegment] = []
        current_time = 0.0
        index = 1

        for line in lines:
            speaker, text = self._extract_speaker(line)

            # 長い発言はブロック分割する
            blocks = self._split_into_blocks(text)

            for block in blocks:
                duration = len(block) * self.SECONDS_PER_CHAR
                duration = max(duration, 1.5)   # 最低1.5秒は表示する

                segments.append(SubtitleSegment(
                    index=index,
                    start_seconds=current_time,
                    end_seconds=current_time + duration,
                    speaker=speaker,
                    text=block,
                ))
                current_time += duration
                index += 1

        return segments

    def _extract_speaker(self, line: str) -> tuple[str, str]:
        """
        1行から話者名と発言テキストを抽出する。
        「山田：こんにちは」→ ("山田", "こんにちは")
        話者名がなければ ("", 行全体)
        """
        match = self.SPEAKER_PATTERN.match(line)
        if match:
            speaker = match.group(1)
            text = line[match.end():]
            return speaker, text
        return "", line

    def _split_into_blocks(self, text: str) -> list[str]:
        """
        テキストを最大文字数ごとに分割する。
        句読点・読点の位置で自然に区切ることを優先する。
        """
        if len(text) <= self.MAX_CHARS_PER_BLOCK:
            return [text]

        blocks: list[str] = []
        remaining = text

        while len(remaining) > self.MAX_CHARS_PER_BLOCK:
            # 最大文字数以内で句読点を探す
            cut_at = self.MAX_CHARS_PER_BLOCK
            for punct_pos in range(self.MAX_CHARS_PER_BLOCK - 1, 0, -1):
                if remaining[punct_pos] in "。、．，!！?？":
                    cut_at = punct_pos + 1
                    break

            blocks.append(remaining[:cut_at])
            remaining = remaining[cut_at:].strip()

        if remaining:
            blocks.append(remaining)

        return blocks

    # ─── フォーマット変換 ─────────────────────────────────────

    def _segments_to_srt(self, segments: list[SubtitleSegment]) -> str:
        """SubtitleSegment リストをSRT文字列に変換する"""
        lines: list[str] = []

        for seg in segments:
            start = self._seconds_to_srt_timestamp(seg.start_seconds)
            end = self._seconds_to_srt_timestamp(seg.end_seconds)
            text = f"[{seg.speaker}] {seg.text}" if seg.speaker else seg.text

            lines.append(str(seg.index))
            lines.append(f"{start} --> {end}")
            lines.append(text)
            lines.append("")   # 空行でブロックを区切る

        return "\n".join(lines)

    def _segments_to_vtt(self, segments: list[SubtitleSegment]) -> str:
        """SubtitleSegment リストをWebVTT文字列に変換する"""
        lines: list[str] = ["WEBVTT", ""]

        for seg in segments:
            start = self._seconds_to_vtt_timestamp(seg.start_seconds)
            end = self._seconds_to_vtt_timestamp(seg.end_seconds)
            text = f"[{seg.speaker}] {seg.text}" if seg.speaker else seg.text

            lines.append(f"{start} --> {end}")
            lines.append(text)
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _seconds_to_srt_timestamp(seconds: float) -> str:
        """秒数をSRT形式のタイムスタンプ（HH:MM:SS,mmm）に変換する"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    @staticmethod
    def _seconds_to_vtt_timestamp(seconds: float) -> str:
        """秒数をWebVTT形式のタイムスタンプ（HH:MM:SS.mmm）に変換する"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
