"""
Microsoft Edge TTS を使ってアバターセリフ音声を生成するサービス。

- edge-tts パッケージが未インストールでも起動でき、その場合は無音で続行する
- キャラクターごとに声質・話速を変えて個性を出す
- 会議参加者モードでは参加者ごとに異なる声を割り当てる
"""

import asyncio
import sys
import time
from pathlib import Path

from loguru import logger

try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False

# Windows では SelectorEventLoop を使わないと edge-tts が動作しない
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# キャラクター別 (voice, rate, pitch)
CHARACTER_VOICE_SETTINGS: dict[str, tuple[str, str, str]] = {
    "ハカセ":       ("ja-JP-KeitaNeural",   "+0%",  "+0Hz"),
    "ツッコミちゃん": ("ja-JP-NanamiNeural", "+10%", "+2Hz"),
    "まとめロボ":   ("ja-JP-KeitaNeural",   "-15%", "-5Hz"),
}
DEFAULT_VOICE = ("ja-JP-NanamiNeural", "+0%", "+0Hz")

# 会議参加者に割り当てる音声リスト（男女交互）
MEETING_VOICES: list[tuple[str, str, str]] = [
    ("ja-JP-KeitaNeural",   "+0%",  "+0Hz"),   # 男性1
    ("ja-JP-NanamiNeural",  "+0%",  "+0Hz"),   # 女性1
    ("ja-JP-KeitaNeural",   "+5%",  "+2Hz"),   # 男性2（やや高め）
    ("ja-JP-NanamiNeural",  "-5%",  "-2Hz"),   # 女性2（やや落ち着いた）
    ("ja-JP-KeitaNeural",   "-5%",  "-2Hz"),   # 男性3（落ち着いた）
    ("ja-JP-NanamiNeural",  "+8%",  "+3Hz"),   # 女性3（元気）
    ("ja-JP-KeitaNeural",   "+8%",  "+3Hz"),   # 男性4（元気）
    ("ja-JP-NanamiNeural",  "-8%",  "-3Hz"),   # 女性4（低め）
]


class TTSService:
    """アバタースクリプトのテキストから MP3 ファイルを生成するサービス"""

    def is_available(self) -> bool:
        return HAS_EDGE_TTS

    # ─── 会議参加者モード ────────────────────────────────────────

    def generate_for_speaker_turns(
        self,
        speaker_turns: list[dict],
        speakers: list[str],
        output_dir: Path,
    ) -> list[dict]:
        """
        会議参加者の発言ターンごとに TTS 音声を生成する。
        参加者ごとに異なる声を割り当てる。

        Returns:
            speaker_turns に 'audio_path' フィールドを追加したリスト
        """
        if not HAS_EDGE_TTS:
            logger.warning("edge-tts 未インストール – TTS をスキップします")
            return [dict(t) | {"audio_path": None} for t in speaker_turns]

        # 参加者 → 音声設定のマップを構築
        voice_map: dict[str, tuple[str, str, str]] = {}
        for i, spk in enumerate(speakers):
            voice_map[spk] = MEETING_VOICES[i % len(MEETING_VOICES)]

        # 全ターンを1つの event loop で処理
        return asyncio.run(self._generate_turns(speaker_turns, voice_map, output_dir))

    async def _generate_turns(
        self,
        turns: list[dict],
        voice_map: dict[str, tuple[str, str, str]],
        output_dir: Path,
    ) -> list[dict]:
        """会議ターン TTS を非同期で全件生成"""
        result: list[dict] = []
        for i, turn in enumerate(turns):
            speaker = turn.get("speaker", "")
            text = turn.get("text", "")
            voice, rate, pitch = voice_map.get(speaker, DEFAULT_VOICE)
            audio_path = output_dir / f"turn_{i:03d}.mp3"

            success = False
            for attempt in range(3):
                try:
                    await self._synthesize(text, voice, rate, pitch, audio_path)
                    if audio_path.exists() and audio_path.stat().st_size > 512:
                        success = True
                        break
                    logger.warning("TTS ターン空 – リトライ", speaker=speaker, attempt=attempt + 1)
                except Exception as err:
                    logger.warning("TTS ターン失敗 – リトライ", speaker=speaker, attempt=attempt + 1, error=str(err))
                await asyncio.sleep(0.8)

            if success:
                logger.info("TTS ターン完了", speaker=speaker, size_kb=round(audio_path.stat().st_size / 1024, 1))
                result.append(dict(turn) | {"audio_path": str(audio_path)})
            else:
                logger.warning("TTS ターン最終失敗", speaker=speaker)
                result.append(dict(turn) | {"audio_path": None})

        return result

    # ─── アバタースクリプトモード ────────────────────────────────

    def generate_for_scripts(
        self,
        scripts: list[dict],
        output_dir: Path,
    ) -> list[dict]:
        """
        avatar_scripts（start_seconds 付き）に対して TTS 音声を生成する。

        Returns:
            scripts に 'audio_path' フィールドを追加したリスト。
            生成失敗時は audio_path = None。
        """
        if not HAS_EDGE_TTS:
            logger.warning("edge-tts 未インストール – TTS をスキップします")
            return [dict(s) | {"audio_path": None} for s in scripts]

        # 全スクリプトを1つの event loop でまとめて処理（複数回 asyncio.run は不安定）
        return asyncio.run(self._generate_all(scripts, output_dir))

    async def _generate_all(self, scripts: list[dict], output_dir: Path) -> list[dict]:
        """全スクリプトの TTS を非同期でまとめて生成する"""
        result: list[dict] = []
        for i, script in enumerate(scripts):
            char = script.get("character_name", "")
            text = script.get("script_text", "")
            voice, rate, pitch = CHARACTER_VOICE_SETTINGS.get(char, DEFAULT_VOICE)
            audio_path = output_dir / f"tts_{i:02d}.mp3"

            success = False
            for attempt in range(3):  # 最大 3 回試みる
                try:
                    await self._synthesize(text, voice, rate, pitch, audio_path)
                    if audio_path.exists() and audio_path.stat().st_size > 1024:
                        success = True
                        break
                    logger.warning("TTS 出力が空 – リトライ", char=char, attempt=attempt + 1)
                except Exception as err:
                    logger.warning("TTS 生成失敗 – リトライ", char=char, attempt=attempt + 1, error=str(err))
                await asyncio.sleep(1.0)  # リトライ間隔

            if success:
                enriched = dict(script) | {"audio_path": str(audio_path)}
                logger.info("TTS 生成完了", char=char, file=audio_path.name, size_kb=round(audio_path.stat().st_size / 1024, 1))
            else:
                logger.warning("TTS 生成最終失敗 – スキップ", char=char)
                enriched = dict(script) | {"audio_path": None}

            result.append(enriched)
        return result

        return result

    @staticmethod
    async def _synthesize(
        text: str,
        voice: str,
        rate: str,
        pitch: str,
        output_path: Path,
    ) -> None:
        communicate = edge_tts.Communicate(text, voice=voice, rate=rate, pitch=pitch)
        await communicate.save(str(output_path))
