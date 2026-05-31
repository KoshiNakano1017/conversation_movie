"""
SubtitleService のユニットテスト。
外部依存なし（純粋な文字列変換ロジックのテスト）。
"""

import pytest

from app.services.subtitle_service import SubtitleService


@pytest.fixture
def service() -> SubtitleService:
    return SubtitleService()


# ─── 話者抽出テスト ────────────────────────────────────────────


class TestExtractSpeaker:
    def test_japanese_colon(self, service: SubtitleService) -> None:
        """日本語コロン「：」で話者名を検出できる"""
        speaker, text = service._extract_speaker("山田：こんにちは")
        assert speaker == "山田"
        assert text == "こんにちは"

    def test_english_colon(self, service: SubtitleService) -> None:
        """英語コロン「:」で話者名を検出できる"""
        speaker, text = service._extract_speaker("Alice: Hello there")
        assert speaker == "Alice"
        assert text == "Hello there"

    def test_no_speaker(self, service: SubtitleService) -> None:
        """話者名がない場合は空文字を返す"""
        speaker, text = service._extract_speaker("普通のテキスト行です")
        assert speaker == ""
        assert text == "普通のテキスト行です"

    def test_speaker_with_space(self, service: SubtitleService) -> None:
        """話者名の後のスペースはテキストに含めない"""
        speaker, text = service._extract_speaker("田中太郎：  内容があります")
        assert speaker == "田中太郎"
        assert text == "内容があります"


# ─── ブロック分割テスト ────────────────────────────────────────


class TestSplitIntoBlocks:
    def test_short_text_is_not_split(self, service: SubtitleService) -> None:
        """最大文字数以下のテキストは分割しない"""
        blocks = service._split_into_blocks("短いテキスト")
        assert len(blocks) == 1
        assert blocks[0] == "短いテキスト"

    def test_long_text_is_split(self, service: SubtitleService) -> None:
        """最大文字数を超えるテキストは複数ブロックに分割する"""
        long_text = "あ" * 100
        blocks = service._split_into_blocks(long_text)
        assert len(blocks) > 1
        for block in blocks:
            assert len(block) <= service.MAX_CHARS_PER_BLOCK

    def test_split_prefers_punctuation(self, service: SubtitleService) -> None:
        """句読点の位置で分割を優先する"""
        text = "これは最初の文です。" + "続きの文章が来ます。" + "さらに続きます。"
        blocks = service._split_into_blocks(text)
        # 句読点で分割されるため、各ブロックの末尾が「。」になるはず
        assert blocks[0].endswith("。")


# ─── SRT生成テスト ────────────────────────────────────────────


class TestGenerateSrt:
    def test_basic_srt_format(self, service: SubtitleService) -> None:
        """SRT形式の基本構造を確認する"""
        transcript = "山田：こんにちは。\n鈴木：よろしくお願いします。"
        srt = service.generate_srt(transcript)

        assert "1\n" in srt
        assert " --> " in srt

    def test_speaker_label_included(self, service: SubtitleService) -> None:
        """話者名が字幕テキストに含まれる"""
        transcript = "山田：テストの発言です。"
        srt = service.generate_srt(transcript)
        assert "[山田]" in srt

    def test_empty_transcript_returns_empty(self, service: SubtitleService) -> None:
        """空のトランスクリプトは空のSRTを返す"""
        srt = service.generate_srt("")
        assert srt.strip() == ""

    def test_no_speaker_transcript(self, service: SubtitleService) -> None:
        """話者なしのテキストも正常にSRTを生成する"""
        transcript = "これは話者なしのテキストです。"
        srt = service.generate_srt(transcript)
        assert " --> " in srt
        assert "[" not in srt   # 話者ラベルは含まれない


# ─── タイムスタンプ変換テスト ─────────────────────────────────


class TestTimestampConversion:
    def test_zero_seconds(self, service: SubtitleService) -> None:
        result = service._seconds_to_srt_timestamp(0.0)
        assert result == "00:00:00,000"

    def test_one_hour(self, service: SubtitleService) -> None:
        result = service._seconds_to_srt_timestamp(3600.0)
        assert result == "01:00:00,000"

    def test_with_milliseconds(self, service: SubtitleService) -> None:
        result = service._seconds_to_srt_timestamp(65.5)
        assert result == "00:01:05,500"

    def test_vtt_uses_dot_separator(self, service: SubtitleService) -> None:
        """VTT形式はミリ秒区切りがドット"""
        result = service._seconds_to_vtt_timestamp(1.234)
        assert "." in result
        assert "," not in result
