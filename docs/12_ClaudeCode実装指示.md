# Claude Code向け実装指示書
## ConversationMovie

**文書バージョン**: 1.0.0  
**作成日**: 2026-05-19  
**用途**: Claude Code / Cursor AIエージェントへの実装指示

**更新メモ（2026-05-23）**: 入力仕様として、音声ファイルアップロードに加えてトランスクリプトファイルアップロード（`.txt` / `.md` / `.srt` / `.vtt`）対応を必須とする。

---

## プロジェクト概要（コンテキスト）

あなたはConversationMovieというサービスのバックエンドを実装します。

**技術スタック**:
- Python 3.11, FastAPI, Celery, Redis
- Supabase (PostgreSQL + Auth + Storage)
- Whisper (音声文字起こし), pyannote.audio (話者分離)
- Gemini 1.5 Flash API (AI分析)
- Remotion + Node.js (動画生成), FFmpeg (字幕合成)
- YouTube Data API v3

**コーディング規約**:
- 型ヒントを必ず付ける
- docstringはGoogle形式
- 非同期処理はasync/awaitを使用
- エラーはカスタム例外クラスで管理
- ロギングはloguru使用
- テストはpytest

---

## 実装指示 #1: プロジェクト全体の骨格作成

```
以下のファイル構成でプロジェクトを初期化してください。

【作成するファイル一覧】
- backend/requirements.txt
- backend/requirements-dev.txt
- backend/Dockerfile
- docker-compose.yml
- .env.example
- Makefile
- backend/app/__init__.py
- backend/app/main.py
- backend/app/config.py
- backend/app/celery_app.py
- backend/app/deps.py
- backend/app/core/__init__.py
- backend/app/core/database.py
- backend/app/core/supabase_client.py
- backend/app/core/security.py
- backend/app/core/exceptions.py
- backend/app/core/logging.py

【requirements.txtの内容】
fastapi[all]==0.115.5
uvicorn[standard]==0.32.1
celery[redis]==5.4.0
redis==5.2.1
sqlalchemy==2.0.36
alembic==1.14.0
supabase==2.10.0
python-jose[cryptography]==3.3.0
python-multipart==0.0.20
pydantic-settings==2.7.0
httpx==0.28.1
flower==2.0.1
loguru==0.7.3
openai-whisper==20240930
google-generativeai==0.8.3
google-api-python-client==2.154.0
google-auth-httplib2==0.2.0
google-auth-oauthlib==1.2.1

【config.pyの実装方針】
pydantic-settingsのBaseSettingsを継承。
.envファイルから設定を読み込む。
以下の設定クラスを作成:
class Settings(BaseSettings):
    # App
    APP_ENV: str = "development"
    APP_SECRET_KEY: str
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    
    # Supabase
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str
    DATABASE_URL: str  # PostgreSQL接続URL
    
    # Gemini
    GEMINI_API_KEY: str
    
    # YouTube
    YOUTUBE_CLIENT_ID: str
    YOUTUBE_CLIENT_SECRET: str
    YOUTUBE_REDIRECT_URI: str
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Whisper
    WHISPER_MODEL: str = "medium"
    WHISPER_DEVICE: str = "cpu"
    
    # Storage
    MEDIA_DIR: str = "/app/media"
    MAX_UPLOAD_SIZE_MB: int = 500
    
    # Remotion
    REMOTION_PROJECT_PATH: str = "../remotion"
    NODE_PATH: str = "/usr/bin/node"

【main.pyの実装方針】
- FastAPIインスタンスにタイトル・バージョン・説明を設定
- CORSミドルウェアを追加（開発時は全オリジン許可）
- 全APIルーターをインクルード
- Jinja2テンプレートの設定
- 静的ファイルのマウント
- /health エンドポイント（DB/Redis/Supabase接続確認）
- スタートアップイベントでモデルの事前ロード
```

---

## 実装指示 #2: データベースモデルとマイグレーション

```
以下のSQLAlchemyモデルを実装してください。
DB設計書（docs/05_DB設計.md）のスキーマに従ってください。

【作成するファイル】
- backend/app/models/__init__.py
- backend/app/models/base.py
- backend/app/models/user.py
- backend/app/models/job.py
- backend/app/models/audio_file.py
- backend/app/models/transcription.py
- backend/app/models/speaker_segment.py
- backend/app/models/analysis.py
- backend/app/models/subtitle.py
- backend/app/models/avatar_character.py
- backend/app/models/avatar_script.py
- backend/app/models/video.py
- backend/app/models/youtube_publication.py
- backend/app/models/job_log.py
- backend/alembic/env.py
- backend/alembic/versions/001_initial_schema.py

【base.pyの内容】
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, DateTime
from sqlalchemy.sql import func

class Base(DeclarativeBase):
    pass

class TimestampMixin:
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

【job.pyのJobStatusEnum】
import enum
class JobStatus(str, enum.Enum):
    PENDING = "pending"
    UPLOADING = "uploading"
    TRANSCRIBING = "transcribing"
    DIARIZING = "diarizing"
    ANALYZING = "analyzing"
    GENERATING_SUBTITLES = "generating_subtitles"
    GENERATING_VIDEO = "generating_video"
    GENERATING_SHORTS = "generating_shorts"
    UPLOADING_YOUTUBE = "uploading_youtube"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

【マイグレーション方針】
Alembicのautogenerateを使わず、
手動でRevisionファイルを作成して確実に管理する。
Supabase RLSポリシーもマイグレーションに含める。
```

---

## 実装指示 #3: Whisper文字起こしサービス

```
Whisperを使った文字起こしサービスを実装してください。

【ファイル】backend/app/services/transcription_service.py

【クラス設計】
class TranscriptionService:
    def __init__(self):
        # シングルトンでモデルをキャッシュ（起動時に1回だけロード）
        self._model = None
    
    def _get_model(self):
        if self._model is None:
            self._model = whisper.load_model(
                settings.WHISPER_MODEL,
                device=settings.WHISPER_DEVICE
            )
        return self._model
    
    async def transcribe(
        self, 
        audio_path: str,
        language: str = "ja"
    ) -> TranscriptionResult:
        """
        音声ファイルを文字起こしする。
        
        Returns:
            TranscriptionResult:
                full_text: str
                segments: list of {
                    id, start, end, text, 
                    words: [{word, start, end, probability}]
                }
                language: str
                duration: float
        """
        # whisper.transcribeを非同期で実行（run_in_executor使用）
        # word_timestamps=True で単語レベルのタイムスタンプを取得

【Celeryワーカー】backend/app/workers/transcription_worker.py

@celery_app.task(
    name="transcription.transcribe_audio",
    queue="ai",
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def transcribe_audio_task(job_id: str) -> dict:
    """
    処理フロー:
    1. JobのstatusをTRANSCRIBINGに更新
    2. audio_filesテーブルからファイル情報を取得
    3. Supabase Storageから音声ファイルをダウンロード (/app/media/にローカル保存)
    4. TranscriptionServiceで文字起こし実行
    5. transcriptionsテーブルに結果を保存
    6. JobのstatusをDIARIZINGに更新、progressを30に更新
    7. WebSocket通知: {event: "step_completed", step: "transcription"}
    8. 次のタスク（diarization_taskまたはanalysis_task）をキューに投入
    9. ローカルの一時ファイルを削除
    """
```

---

## 実装指示 #4: Gemini AI分析サービス

```
Gemini APIを使ったAI分析サービスを実装してください。

【ファイル】backend/app/services/gemini_service.py

【重要な実装方針】
- 1回のAPIコールで要約・テーマ・感情・名言を全て取得（コスト最適化）
- レスポンスはJSON形式で要求し、pydanticで検証
- レート制限は指数バックオフで対応
- プロンプトはprompts/ディレクトリで管理

【analyze_conversation メソッド】
async def analyze_conversation(
    self,
    transcript: str,
    language: str = "ja"
) -> ConversationAnalysis:
    """
    文字起こしテキストからAI分析を実行。
    
    プロンプトの要点:
    - システムプロンプト: 会議分析の専門家として振る舞うよう指示
    - ユーザープロンプト: テキストと期待するJSON出力形式を提示
    - 出力JSONのスキーマを詳細に指定（必須フィールドと型）
    - 日本語での出力を明示
    
    Returns: ConversationAnalysis (pydanticモデル)
    """

【generate_avatar_scripts メソッド】
async def generate_avatar_scripts(
    self,
    analysis: ConversationAnalysis,
    duration_seconds: float
) -> list[AvatarScriptItem]:
    """
    会議の長さに応じて適切な長さのセリフを生成。
    
    キャラクター設定:
    - ハカセ (hakase): 知的・丁寧な解説
    - ツッコミちゃん (tsukkomi): 驚き・共感リアクション  
    - まとめロボ (matomerobo): 端的なまとめ
    
    各キャラクターが1〜3セリフを担当。
    合計セリフ時間 = 元動画の長さに比例（最小2分）
    """

【エラーハンドリング】
- google.api_core.exceptions.ResourceExhausted → 60秒待機してリトライ
- google.api_core.exceptions.InvalidArgument → ConversationMovieError を raise
- JSONパース失敗 → プロンプトを修正して再試行（最大2回）
```

---

## 実装指示 #5: 動画生成パイプライン

```
Remotion + FFmpegによる動画生成を実装してください。

【Remotion側の実装】

remotion/src/types/video-data.ts:
export interface VideoData {
  title: string;
  duration: number;  // 動画の総フレーム数
  fps: number;       // 30
  subtitles: SubtitleSegment[];
  avatarScripts: AvatarScript[];
  analysis: {
    summary: string;
    themes: string[];
    quotes: Quote[];
  };
}

remotion/src/compositions/AvatarVideo.tsx:
- durationInFrames は VideoData.duration を使用
- 構成:
  1. イントロ (3秒): タイトルカード
  2. 要約セクション (アバターが要約を語る)
  3. 名言セクション (名言カードを表示)
  4. アウトロ (2秒): キーワードタグ表示
- 字幕は常に画面下部に表示（VideoData.subtitlesと同期）

【バックエンド側の実装】

backend/app/services/video_service.py:

class VideoService:
    async def render_video(
        self,
        job_id: str,
        video_data: VideoData,
        output_type: Literal["full", "shorts"] = "full"
    ) -> str:  # 出力ファイルパスを返す
        """
        1. VideoDataをJSONファイルとして一時保存
        2. Remotion CLIをサブプロセスで実行:
           npx remotion render \\
             --config=remotion.config.ts \\
             AvatarVideo \\
             {output_path} \\
             --props={json_path}
        3. サブプロセスの標準出力をロギング
        4. 完了後に一時JSONファイルを削除
        5. 出力MP4パスを返す
        """
    
    async def add_subtitles(
        self,
        video_path: str,
        srt_path: str,
        output_path: str
    ) -> str:
        """
        FFmpegで字幕を焼き込む:
        ffmpeg -i {video} -vf subtitles={srt} \\
          -c:a copy {output}
        """
    
    async def generate_thumbnail(
        self,
        video_path: str,
        output_path: str,
        time_seconds: float = 3.0
    ) -> str:
        """
        FFmpegで指定時刻のフレームをJPEGで抽出
        """

【workers/video_worker.py の処理フロー】
1. JobのstatusをGENERATING_VIDEOに更新
2. analysesとavatar_scriptsをDBから取得
3. subtitlesをDBから取得
4. VideoDataオブジェクトを構築
5. VideoServiceでMP4レンダリング
6. VideoServiceで字幕を焼き込み
7. VideoServiceでサムネイル生成
8. Supabase Storageにアップロード
9. videosテーブルに保存
10. JobのstatusをUPLOADING_YOUTUBEに更新
11. WebSocket通知
```

---

## 実装指示 #6: YouTube投稿サービス

```
YouTube Data API v3を使った投稿機能を実装してください。

【ファイル】backend/app/services/youtube_service.py

【OAuth認証フロー】
class YouTubeService:
    def get_auth_url(self, user_id: str) -> str:
        """
        PKCE対応のOAuth2認証URLを生成。
        stateパラメータにuser_idをJWTで埋め込む（CSRF対策）
        """
    
    async def handle_callback(
        self,
        code: str,
        state: str
    ) -> tuple[str, Credentials]:
        """
        認証コードを使ってトークンを取得。
        Returns: (user_id, credentials)
        """
    
    async def save_credentials(
        self,
        user_id: str,
        credentials: Credentials
    ) -> None:
        """
        refresh_tokenをFernet対称暗号で暗号化してDB保存
        APP_SECRET_KEYから暗号化キーを派生
        """
    
    async def upload_video(
        self,
        user_id: str,
        video_path: str,
        title: str,
        description: str,
        tags: list[str],
        privacy_status: str = "private",
        is_shorts: bool = False
    ) -> str:  # YouTube動画IDを返す
        """
        再開可能なアップロード（ResumableUpload）を使用。
        大きなファイルでも確実にアップロードできる。
        進捗をログに出力。
        
        Shorts向けの処理:
        - tagsに"Shorts"を追加
        - descriptionに"#Shorts"を追加
        """

【エラーハンドリング】
- HttpError 403 (quotaExceeded) → 翌日まで待機を通知
- HttpError 401 → 再認証を促す
- ネットワークエラー → リトライ（最大5回）
- アップロード中断 → resumeTokenを保存して再開可能に
```

---

## 実装指示 #7: WebSocketリアルタイム通知

```
WebSocketを使ったリアルタイム進捗通知を実装してください。

【ファイル】
- backend/app/services/notification_service.py
- backend/app/api/websocket.py

【ConnectionManager の設計】
class ConnectionManager:
    def __init__(self):
        # job_id -> set[WebSocket] のマッピング
        self.active_connections: dict[str, set[WebSocket]] = {}
    
    async def connect(self, job_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.setdefault(job_id, set()).add(websocket)
    
    def disconnect(self, job_id: str, websocket: WebSocket):
        if job_id in self.active_connections:
            self.active_connections[job_id].discard(websocket)
    
    async def broadcast_to_job(self, job_id: str, message: dict):
        """job_idに接続している全WebSocketにメッセージを送信"""
        # 送信失敗したWebSocketは自動的に切断リストに追加

【CeleryワーカーからのWebSocket通知方法】
Celeryワーカーはイベントループを持たないため、
Redisのpub/subを介してFastAPIにメッセージを中継する。

Worker → Redis Pub/Sub → FastAPI WebSocket Handler → ブラウザ

実装:
1. Celeryワーカーは redis_client.publish(f"job:{job_id}", json_message) で送信
2. FastAPIのWebSocketハンドラーはRedisのSubscriberを非同期ループで監視
3. メッセージを受信したらWebSocketにブロードキャスト

【通知メッセージ形式】
{
  "event": "step_completed",
  "data": {
    "step": "transcription",
    "status": "completed",
    "progress": 30,
    "message": "文字起こしが完了しました（3,245文字）",
    "result": { ... }  // ステップに応じた結果データ
  }
}
```

---

## 実装指示 #8: フロントエンドテンプレート

```
以下のHTMLテンプレートをJinja2 + Tailwind CSSで実装してください。

デザイン方針:
- カラーパレット: プライマリ #6366f1 (indigo-500), セカンダリ #a855f7 (purple-500)
- フォント: Google Fonts 'Noto Sans JP'
- アイコン: Heroicons (CDN経由)
- アニメーション: Tailwind CSS transitions
- かわいさ: 丸みのあるカード, グラデーション, やわらかい影

【templates/base.html】
- ナビゲーション（ロゴ + メニュー + ユーザーアイコン + ログアウト）
- トースト通知システム（JS）
- WebSocket接続管理（グローバル）
- Tailwind + Heroicons CDN読み込み

【templates/upload.html】
- ドラッグ&ドロップゾーン（点線ボーダー、ホバー時に色変化）
- ファイル選択後のファイル名・サイズ表示
- アップロード中のプログレスバー（Fetch APIのupload.onprogress）
- フォーム: タイトル（必須）、説明（任意）、話者数（セレクトボックス）

【templates/job_detail.html】
- ステップリスト（縦並び、各ステップにアイコン・ラベル・ステータス）
- プログレスサークルまたはバー
- WebSocketでリアルタイム更新（JavaScriptでDOMを更新）
- 完了時に「動画プレビューを見る」ボタンをアニメーション付きで表示

【templates/job_preview.html】
- 左カラム(60%): 動画プレイヤー（カスタムコントロール）
- 右カラム(40%): 分析結果（タブ: 要約/テーマ/名言）
- 下部: 字幕テキスト（スクロール同期 - 任意）
- アクションバー: 「ダウンロード」「YouTube投稿へ」ボタン

【templates/publish.html】
- フォーム: タイトル（テキストエリア）、説明（テキストエリア）、タグ（タグ入力UI）
- 公開設定: ラジオボタン3択（アイコン付き）
- プレビュー: YouTubeのサムネイルと説明のモック表示
- 投稿ボタン（クリック後にローディング状態）
```

---

## 実装指示 #9: Remotion動画テンプレート（詳細）

```
Remotionのコンポーネントを実装してください。

【前提】
- Node.js 18+, React 18
- @remotion/cli, remotion パッケージ使用
- TypeScript strict mode

【remotion/src/components/Avatar/Avatar.tsx】

Props:
- characterId: "hakase" | "tsukkomi" | "matomerobo"
- expression: "default" | "talking" | "surprised"
- position: "left" | "right" | "center"
- scale: number (default 1.0)

実装:
- useCurrentFrame() でフレームを取得
- spring() アニメーションで登場アニメーション
- interpolate() で口パクアニメーション（talkingのとき）
- アバター画像はpublicディレクトリから読み込み

【remotion/src/components/Subtitle/SubtitleOverlay.tsx】

Props:
- subtitles: Array<{start: number, end: number, text: string, speaker?: string}>
- fps: number

実装:
- useCurrentFrame() で現在フレームを取得
- 現在フレームに対応する字幕を filter() で選択
- 字幕テキストをフェードイン/アウト
- 話者名を左端に表示（色分け）
- 最大2行表示、長い場合は折り返し

【remotion/src/compositions/AvatarVideo.tsx】

Timeline設計（例: 60分音声の場合）:
- Frame 0-90 (3秒): イントロ
  - タイトルがフェードイン
  - 背景グラデーションアニメーション
  
- Frame 90-: メインコンテンツ
  - アバターが登場（スライドイン）
  - 字幕と連動してセリフを表示
  - キャラクターが交互に登場
  
- 最終60フレーム (2秒): アウトロ
  - キーワードタグがポップアップ
  - "この動画はAIで生成されました" テキスト

【バックエンドとの連携】
動画データはJSONファイルとして渡す:
npx remotion render AvatarVideo output.mp4 \\
  --props='{"title":"...", "subtitles":[...], ...}'

または --props=./video_data.json で渡す
```

---

## 実装指示 #10: テストとCI/CD

```
テストとCI/CDを実装してください。

【backend/tests/conftest.py】
- pytest-asyncio の設定
- テスト用インメモリSQLiteまたはテスト用PostgreSQL
- Supabase/YouTube APIのモック
- サンプル音声ファイルのフィクスチャ
- テスト用ユーザー・ジョブのフィクスチャ

【backend/tests/unit/test_subtitle_service.py】
テストケース:
1. 正常系: セグメントリストからSRTが生成される
2. 話者ラベル付きSRT
3. 長いテキストの折り返し
4. タイムスタンプのフォーマット検証
5. 空のセグメントリスト（エラー or 空文字）

【backend/tests/unit/test_gemini_service.py】
- unittest.mock でGemini APIをモック
- 正常なJSONレスポンスのパース
- 不正なJSONへの対応
- レート制限エラーのリトライ

【.github/workflows/ci.yml】
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      redis:
        image: redis:7
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: python-version: '3.11'
      - run: pip install -r backend/requirements-dev.txt
      - run: cd backend && pytest tests/ -v --cov=app
      - run: cd backend && ruff check app/
      - run: cd backend && mypy app/ --ignore-missing-imports
```

---

## 実装の注意事項

### セキュリティ
- APIキーは絶対にハードコードしない
- YouTubeのrefresh_tokenは暗号化して保存（`cryptography.fernet`）
- SQLインジェクション対策: SQLAlchemy ORMを使う（生クエリ禁止）
- ファイルアップロード: パス traversal攻撃対策（`os.path.basename`）

### コスト最適化
- Gemini APIは1回のコールで全分析を取得
- Whisperはモデルをキャッシュ（起動時1回だけロード）
- Supabase Storageは古いファイルを自動削除
- YouTubeアップロードは非同期（ブロッキングしない）

### エラー設計
```python
# backend/app/core/exceptions.py

class ConversationMovieError(Exception):
    """ベース例外クラス"""
    def __init__(self, code: str, message: str, detail: str = ""):
        self.code = code
        self.message = message
        self.detail = detail

class AudioValidationError(ConversationMovieError): pass
class TranscriptionError(ConversationMovieError): pass
class DiarizationError(ConversationMovieError): pass
class GeminiAnalysisError(ConversationMovieError): pass
class VideoGenerationError(ConversationMovieError): pass
class YouTubeError(ConversationMovieError): pass
class StorageError(ConversationMovieError): pass
```

### ログ設計
```python
from loguru import logger

# 全サービスでこの形式を使用
logger.info("文字起こし開始", job_id=job_id, model=model_name)
logger.error("Gemini API失敗", job_id=job_id, error=str(e), retry_count=retry)
```

---

*実装指示書終端*
