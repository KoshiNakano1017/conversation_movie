"""
Gemini APIを使った会議分析サービス。

設計方針:
- 1回のAPIコールで全分析を取得（コスト・速度を最適化）
- レート制限（15RPM）に対して指数バックオフでリトライ
- レスポンスのJSONパースに失敗した場合はフォールバック値を返す

生成プロンプト: docs/ai-prompts/gemini_analysis.md
"""

import json
import re
import time
from dataclasses import dataclass, field

import google.generativeai as genai
from loguru import logger

from app.config import settings
from app.core.exceptions import GeminiAnalysisError
from app.prompts.avatar_script_prompt import AVATAR_SCRIPT_PROMPT
from app.prompts.summary_prompt import CONVERSATION_ANALYSIS_PROMPT

# ─── データクラス（API応答の型定義） ──────────────────────────


@dataclass
class ActionItem:
    who: str
    what: str
    when: str = ""


@dataclass
class SummaryDetailed:
    overview: str
    key_decisions: list[str] = field(default_factory=list)
    action_items: list[ActionItem] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)


@dataclass
class Quote:
    speaker: str
    text: str
    reason: str = ""


@dataclass
class ConversationAnalysis:
    """Gemini APIの分析結果をまとめるデータクラス"""
    summary_short: str
    summary_medium: str
    summary_detailed: SummaryDetailed
    themes: list[str]
    keywords: list[str]
    quotes: list[Quote]
    overall_sentiment: str
    suggested_title: str
    suggested_description: str
    suggested_tags: list[str]
    tokens_used: int = 0


@dataclass
class YouTubeMetadata:
    """YouTube投稿向けメタデータ"""
    title: str
    description: str
    tags: list[str]


@dataclass
class AvatarScriptItem:
    """アバターのセリフ1件"""
    character_name: str
    section: str         # intro / summary / quote / outro
    script_text: str
    target_chars: int


# ─── キャラクター定義 ─────────────────────────────────────────

AVATAR_CHARACTERS = [
    {
        "name": "ハカセ",
        "personality": "知識豊富な博士。難しい内容を丁寧に分かりやすく解説するのが得意。「なるほど、これは興味深い！」が口癖。",
        "sections": ["intro", "summary"],
        "chars_per_section": 150,
    },
    {
        "name": "ツッコミちゃん",
        "personality": "明るくてエネルギッシュ。意外な発見に驚き、視聴者と一緒に楽しむ。「え！それどういうこと？」が口癖。",
        "sections": ["quote"],
        "chars_per_section": 120,
    },
    {
        "name": "まとめロボ",
        "personality": "冷静で論理的なロボット。情報を整理してポイントをまとめるのが得意。「ポイントを整理します。」が口癖。",
        "sections": ["outro"],
        "chars_per_section": 100,
    },
]


# ─── Geminiサービス ───────────────────────────────────────────

class GeminiService:
    """
    Gemini APIとのやり取りをすべて管理するサービスクラス。
    シングルトンとして使用することでモデルのロードコストを削減する。
    """

    GEMINI_MODEL = "gemini-2.5-flash"
    MAX_RETRIES = 3
    RETRY_WAIT_SECONDS = 65   # レート制限解除を待つ時間（1分強）

    def __init__(self) -> None:
        if not settings.GEMINI_API_KEY:
            raise GeminiAnalysisError(
                code="GEM001",
                message="GEMINI_API_KEY が設定されていません",
            )
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self._model = genai.GenerativeModel(self.GEMINI_MODEL)

    # ─── 公開メソッド ─────────────────────────────────────────

    def analyze_conversation(
        self,
        transcript: str,
        language: str = "ja",
    ) -> ConversationAnalysis:
        """
        トランスクリプトを分析して ConversationAnalysis を返す。
        レート制限エラー時は指数バックオフでリトライする。

        Args:
            transcript: 分析するトランスクリプト本文
            language: 出力言語（"ja" または "en"）

        Returns:
            ConversationAnalysis: 分析結果

        Raises:
            GeminiAnalysisError: リトライ上限を超えた場合
        """
        prompt = CONVERSATION_ANALYSIS_PROMPT.format(
            transcript=transcript,
            language="日本語" if language == "ja" else "English",
        )

        raw_response = self._call_with_retry(prompt)
        return self._parse_analysis_response(raw_response)

    def generate_avatar_scripts(
        self,
        analysis: ConversationAnalysis,
        title: str,
    ) -> list[AvatarScriptItem]:
        """
        分析結果をもとに各アバターキャラクターのセリフを生成する。
        キャラクターごとに1回のAPIコールを行う。

        Args:
            analysis: analyze_conversation の結果
            title: 会議タイトル

        Returns:
            list[AvatarScriptItem]: キャラクター・セクション別のセリフ一覧
        """
        scripts: list[AvatarScriptItem] = []

        quotes_text = "\n".join(
            f"- {q.speaker}：「{q.text}」" for q in analysis.quotes
        ) or "（名言なし）"

        action_items_text = "\n".join(
            f"- {item.who}：{item.what}"
            for item in analysis.summary_detailed.action_items
        ) or "（アクションアイテムなし）"

        for character in AVATAR_CHARACTERS:
            for section in character["sections"]:
                prompt = AVATAR_SCRIPT_PROMPT.format(
                    character_name=character["name"],
                    personality=character["personality"],
                    title=title,
                    summary_short=analysis.summary_short,
                    themes="、".join(analysis.themes),
                    quotes=quotes_text,
                    action_items=action_items_text,
                    section=section,
                    target_chars=character["chars_per_section"],
                )

                try:
                    script_text = self._call_with_retry(prompt).strip()
                    scripts.append(AvatarScriptItem(
                        character_name=character["name"],
                        section=section,
                        script_text=script_text,
                        target_chars=character["chars_per_section"],
                    ))
                    logger.debug(
                        "アバターセリフ生成完了",
                        character=character["name"],
                        section=section,
                        chars=len(script_text),
                    )
                except GeminiAnalysisError as error:
                    logger.warning(
                        "アバターセリフ生成失敗（スキップ）",
                        character=character["name"],
                        section=section,
                        error=str(error),
                    )

        return scripts

    def generate_youtube_metadata(self, analysis: ConversationAnalysis) -> YouTubeMetadata:
        """
        分析結果からYouTube投稿向けのメタデータを整形して返す。
        """
        title = (analysis.suggested_title or "").strip()
        description = (analysis.suggested_description or "").strip()
        tags = [str(tag).strip() for tag in analysis.suggested_tags if str(tag).strip()]

        if not title:
            title_source = analysis.summary_short or "会議の振り返り"
            title = title_source[:40]
        if not description:
            description = analysis.summary_medium or analysis.summary_short
        if not tags:
            tags = [*analysis.themes[:3], *analysis.keywords[:5]]
            tags = [tag.strip() for tag in tags if tag and tag.strip()]

        title = title[:100]
        description = description[:5000]
        tags = tags[:10]

        return YouTubeMetadata(title=title, description=description, tags=tags)

    # ─── 内部メソッド ─────────────────────────────────────────

    def _call_with_retry(self, prompt: str) -> str:
        """
        Gemini APIを呼び出す。レート制限エラーは指数バックオフでリトライする。

        Args:
            prompt: 送信するプロンプト

        Returns:
            APIのテキストレスポンス
        """
        last_error: Exception | None = None

        for attempt in range(self.MAX_RETRIES):
            try:
                response = self._model.generate_content(
                    prompt,
                    generation_config=genai.GenerationConfig(
                        temperature=0.3,   # 分析タスクは低温度で安定出力
                        max_output_tokens=4096,
                    ),
                )
                return response.text

            except Exception as error:
                last_error = error
                error_message = str(error).lower()

                is_rate_limit = any(
                    keyword in error_message
                    for keyword in ["quota", "rate", "429", "resource exhausted"]
                )

                if is_rate_limit and attempt < self.MAX_RETRIES - 1:
                    wait_seconds = self.RETRY_WAIT_SECONDS * (attempt + 1)
                    logger.warning(
                        "Geminiレート制限。リトライ待機中",
                        attempt=attempt + 1,
                        wait_seconds=wait_seconds,
                    )
                    time.sleep(wait_seconds)
                else:
                    logger.error("Gemini API呼び出し失敗", error=str(error), attempt=attempt + 1)
                    break

        raise GeminiAnalysisError(
            code="GEM002",
            message="Gemini APIの呼び出しに失敗しました",
            detail=str(last_error),
        )

    def _parse_analysis_response(self, raw_text: str) -> ConversationAnalysis:
        """
        Geminiのテキストレスポンスをパースして ConversationAnalysis に変換する。
        JSONパース失敗時はフォールバック値を使用してエラーを防ぐ。
        """
        try:
            data = self._extract_json(raw_text)
            return self._build_analysis_from_dict(data)
        except Exception as error:
            logger.error("Geminiレスポンスのパース失敗", error=str(error), raw=raw_text[:200])
            raise GeminiAnalysisError(
                code="GEM003",
                message="Geminiの応答をパースできませんでした",
                detail=str(error),
            )

    def _extract_json(self, text: str) -> dict:
        """
        テキストからJSONブロックを抽出する。
        Geminiがコードブロックで囲んで返すケースに対応。
        """
        # コードブロック内のJSONを優先して抽出
        code_block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if code_block_match:
            return json.loads(code_block_match.group(1))

        # コードブロックなしで直接JSONが返された場合
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))

        raise ValueError("レスポンスにJSONが見つかりませんでした")

    def _build_analysis_from_dict(self, data: dict) -> ConversationAnalysis:
        """辞書からConversationAnalysisデータクラスを構築する"""
        raw_detailed = data.get("summary_detailed", {})

        action_items = [
            ActionItem(
                who=item.get("who", ""),
                what=item.get("what", ""),
                when=item.get("when", ""),
            )
            for item in raw_detailed.get("action_items", [])
        ]

        summary_detailed = SummaryDetailed(
            overview=raw_detailed.get("overview", ""),
            key_decisions=raw_detailed.get("key_decisions", []),
            action_items=action_items,
            next_steps=raw_detailed.get("next_steps", []),
        )

        quotes = [
            Quote(
                speaker=q.get("speaker", ""),
                text=q.get("text", ""),
                reason=q.get("reason", ""),
            )
            for q in data.get("quotes", [])
        ]

        return ConversationAnalysis(
            summary_short=data.get("summary_short", ""),
            summary_medium=data.get("summary_medium", ""),
            summary_detailed=summary_detailed,
            themes=data.get("themes", []),
            keywords=data.get("keywords", []),
            quotes=quotes,
            overall_sentiment=data.get("overall_sentiment", "neutral"),
            suggested_title=data.get("suggested_title", ""),
            suggested_description=data.get("suggested_description", ""),
            suggested_tags=data.get("suggested_tags", []),
        )
