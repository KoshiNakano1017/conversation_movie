"""
GeminiService のユニットテスト。
外部APIはモックに差し替えてテストする。
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import GeminiAnalysisError
from app.services.gemini_service import GeminiService


VALID_ANALYSIS_JSON = {
    "summary_short": "Q2進捗について話し合いました。",
    "summary_medium": "本日の定例MTGでは、Q2の進捗確認と新機能の優先度について議論しました。",
    "summary_detailed": {
        "overview": "Q2進捗確認MTG",
        "key_decisions": ["機能Aを優先する"],
        "action_items": [{"who": "山田", "what": "デザイン修正", "when": "5/26"}],
        "next_steps": ["次回MTGで進捗確認"],
    },
    "themes": ["Q2進捗", "新機能"],
    "keywords": ["MVP", "ユーザーテスト"],
    "quotes": [
        {"speaker": "山田", "text": "ユーザーを第一に考えましょう", "reason": "プロダクト哲学を表す発言"}
    ],
    "overall_sentiment": "positive",
    "suggested_title": "【会議録】Q2進捗MTG",
    "suggested_description": "Q2の進捗と新機能について議論しました。",
    "suggested_tags": ["会議録", "Q2"],
}


@pytest.fixture
def mock_gemini_service():
    """Geminiクライアントをモックしたサービスインスタンスを返す"""
    with patch("app.services.gemini_service.genai") as mock_genai:
        mock_model = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model

        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}):
            with patch("app.services.gemini_service.settings") as mock_settings:
                mock_settings.GEMINI_API_KEY = "test-key"
                service = GeminiService.__new__(GeminiService)
                service._model = mock_model
                service.MAX_RETRIES = 3
                service.RETRY_WAIT_SECONDS = 0  # テスト中は待機しない

        yield service, mock_model


# ─── _extract_json のテスト ────────────────────────────────────


class TestExtractJson:
    @pytest.fixture
    def service(self):
        with patch("app.services.gemini_service.settings") as mock_settings:
            mock_settings.GEMINI_API_KEY = "test-key"
            with patch("app.services.gemini_service.genai"):
                return GeminiService.__new__(GeminiService)

    def test_extracts_json_from_code_block(self, service: GeminiService) -> None:
        """コードブロックで囲まれたJSONを正しく抽出する"""
        text = '```json\n{"key": "value"}\n```'
        result = service._extract_json(text)
        assert result == {"key": "value"}

    def test_extracts_raw_json(self, service: GeminiService) -> None:
        """コードブロックなしのJSONも抽出できる"""
        text = '{"key": "value"}'
        result = service._extract_json(text)
        assert result == {"key": "value"}

    def test_raises_on_no_json(self, service: GeminiService) -> None:
        """JSONが見つからない場合はValueErrorを送出する"""
        with pytest.raises(ValueError):
            service._extract_json("これはJSONではありません")


# ─── _build_analysis_from_dict のテスト ──────────────────────


class TestBuildAnalysisFromDict:
    @pytest.fixture
    def service(self):
        with patch("app.services.gemini_service.settings") as mock_settings:
            mock_settings.GEMINI_API_KEY = "test-key"
            with patch("app.services.gemini_service.genai"):
                return GeminiService.__new__(GeminiService)

    def test_builds_analysis_from_valid_dict(self, service: GeminiService) -> None:
        """有効な辞書からConversationAnalysisを構築できる"""
        result = service._build_analysis_from_dict(VALID_ANALYSIS_JSON)
        assert result.summary_short == "Q2進捗について話し合いました。"
        assert result.overall_sentiment == "positive"
        assert len(result.quotes) == 1
        assert result.quotes[0].speaker == "山田"

    def test_handles_missing_optional_fields(self, service: GeminiService) -> None:
        """オプションフィールドが欠けていてもエラーにならない"""
        minimal = {
            "summary_short": "短い要約",
            "summary_medium": "中程度の要約",
            "summary_detailed": {},
            "themes": [],
            "keywords": [],
            "quotes": [],
            "overall_sentiment": "neutral",
            "suggested_title": "",
            "suggested_description": "",
            "suggested_tags": [],
        }
        result = service._build_analysis_from_dict(minimal)
        assert result.summary_short == "短い要約"
        assert result.themes == []


# ─── analyze_conversation のテスト ────────────────────────────


class TestAnalyzeConversation:
    def test_returns_analysis_on_success(self, mock_gemini_service) -> None:
        """正常なAPIレスポンスでConversationAnalysisを返す"""
        service, mock_model = mock_gemini_service

        mock_response = MagicMock()
        mock_response.text = json.dumps(VALID_ANALYSIS_JSON)
        mock_model.generate_content.return_value = mock_response

        result = service.analyze_conversation("山田：テストです。", language="ja")

        assert result.summary_short == "Q2進捗について話し合いました。"
        assert result.overall_sentiment == "positive"

    def test_retries_on_rate_limit(self, mock_gemini_service) -> None:
        """レート制限エラー時にリトライする"""
        service, mock_model = mock_gemini_service
        service.RETRY_WAIT_SECONDS = 0  # テスト中は待機しない

        mock_response = MagicMock()
        mock_response.text = json.dumps(VALID_ANALYSIS_JSON)

        # 1回目は失敗、2回目は成功
        mock_model.generate_content.side_effect = [
            Exception("429 Resource Exhausted: quota exceeded"),
            mock_response,
        ]

        result = service.analyze_conversation("テスト", language="ja")
        assert mock_model.generate_content.call_count == 2

    def test_raises_after_max_retries(self, mock_gemini_service) -> None:
        """リトライ上限を超えたらGeminiAnalysisErrorを送出する"""
        service, mock_model = mock_gemini_service
        service.MAX_RETRIES = 2
        service.RETRY_WAIT_SECONDS = 0

        mock_model.generate_content.side_effect = Exception("quota exceeded")

        with pytest.raises(GeminiAnalysisError):
            service.analyze_conversation("テスト", language="ja")


class TestGenerateYouTubeMetadata:
    @pytest.fixture
    def service(self):
        with patch("app.services.gemini_service.settings") as mock_settings:
            mock_settings.GEMINI_API_KEY = "test-key"
            with patch("app.services.gemini_service.genai"):
                return GeminiService.__new__(GeminiService)

    def test_uses_suggested_fields_when_available(self, service: GeminiService) -> None:
        analysis = service._build_analysis_from_dict(VALID_ANALYSIS_JSON)
        metadata = service.generate_youtube_metadata(analysis)
        assert metadata.title == "【会議録】Q2進捗MTG"
        assert "Q2の進捗" in metadata.description
        assert metadata.tags == ["会議録", "Q2"]

    def test_falls_back_when_suggested_fields_missing(self, service: GeminiService) -> None:
        analysis = service._build_analysis_from_dict(
            {
                "summary_short": "短い要約テキスト",
                "summary_medium": "中くらいの要約テキスト",
                "summary_detailed": {},
                "themes": ["テーマA", "テーマB"],
                "keywords": ["k1", "k2", "k3"],
                "quotes": [],
                "overall_sentiment": "neutral",
                "suggested_title": "",
                "suggested_description": "",
                "suggested_tags": [],
            }
        )
        metadata = service.generate_youtube_metadata(analysis)
        assert metadata.title == "短い要約テキスト"
        assert metadata.description == "中くらいの要約テキスト"
        assert metadata.tags[:2] == ["テーマA", "テーマB"]
