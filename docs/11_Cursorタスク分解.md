# Cursor向けタスク分解
## ConversationMovie

**文書バージョン**: 1.0.0  
**作成日**: 2026-05-19  
**用途**: Cursor AIエージェントへの指示・タスク管理

**更新メモ（2026-05-23）**: 音声アップロード系タスクは、トランスクリプトファイルアップロード対応（`.txt` / `.md` / `.srt` / `.vtt`）を前提に実装する。

---

## 使い方

このドキュメントの各タスクをCursorのチャットに貼り付けて実装を依頼してください。  
タスクIDは依存関係の管理に使用します。

---

## Phase 0: インフラ・基盤構築

### TASK-001: プロジェクト初期セットアップ
```
依存: なし
優先度: 最高

以下のファイルを作成してください:

1. backend/requirements.txt
   必要なパッケージ:
   - fastapi[all]==0.115.x
   - uvicorn[standard]
   - celery[redis]
   - redis
   - sqlalchemy
   - alembic
   - supabase
   - python-jose[cryptography]
   - python-multipart
   - pydantic-settings
   - httpx
   - flower

2. docker-compose.yml
   サービス: api, worker-ai, worker-video, worker-upload, redis, flower
   ボリューム: media, models
   ネットワーク: app-network

3. backend/Dockerfile
   ベースイメージ: python:3.11-slim
   ffmpegとnodejsもインストール

4. .env.example
   必要な環境変数を全て列挙

5. Makefile
   dev, test, lint, migrate, logs コマンドを定義
```

### TASK-002: FastAPIアプリ基盤
```
依存: TASK-001
優先度: 最高

backend/app/ 以下を実装してください:

1. main.py
   - FastAPIインスタンス作成
   - CORSミドルウェア設定
   - ルーターの登録
   - /health エンドポイント

2. config.py
   - pydantic-settingsを使用
   - .envから設定を読み込む
   - 必要な設定: DATABASE_URL, SUPABASE_URL, SUPABASE_KEY, GEMINI_API_KEY, REDIS_URL など

3. core/database.py
   - SQLAlchemy設定
   - SessionLocal
   - Base クラス
   - get_db 依存性注入関数

4. core/supabase_client.py
   - Supabaseクライアントの初期化
   - シングルトンパターン
```

### TASK-003: DBマイグレーション設定
```
依存: TASK-002
優先度: 高

1. Alembicの初期化とenv.py設定
2. 以下のモデルをSQLAlchemyで実装:
   - models/user.py (usersテーブル)
   - models/job.py (jobsテーブル, JobStatus enum)
   - models/audio_file.py (audio_filesテーブル)
3. 初回マイグレーションファイルを作成
4. Supabaseで実行するSQL（RLSポリシー含む）を docs/sql/001_init.sql に出力

DB設計書（docs/05_DB設計.md）に従って実装してください。
```

### TASK-004: 認証実装
```
依存: TASK-002, TASK-003
優先度: 高

1. core/security.py
   - Supabase JWTトークンの検証関数
   - get_current_user 依存性注入関数

2. api/auth.py
   - POST /api/auth/google (トークン交換)
   - POST /api/auth/refresh
   - POST /api/auth/logout

3. templates/auth/login.html
   - Googleログインボタン
   - Tailwind CSSでシンプルなデザイン

4. deps.py
   - 認証済みユーザーの取得
   - オプション認証の取得
```

### TASK-005: Celery基盤設定
```
依存: TASK-002
優先度: 高

1. celery_app.py
   - Celeryインスタンス設定
   - Redisブローカー設定
   - タスクキューの定義 (ai, video, upload)
   - タスクのデフォルト設定（リトライ、タイムアウト）

2. workers/__init__.py でタスクを自動検出

3. docker-compose.ymlのworkerサービス設定を確認・修正
   - worker-ai: -Q ai --concurrency=1
   - worker-video: -Q video --concurrency=2
   - worker-upload: -Q upload --concurrency=3
```

---

## Phase 1: コア機能実装

### TASK-006: 入力アップロードAPI（音声/トランスクリプト）
```
依存: TASK-003, TASK-004
優先度: 最高

1. services/storage_service.py
   - Supabase Storageへのファイルアップロード
   - ファイルダウンロード（URLの署名付き生成）
   - ファイル削除

2. services/audio_service.py
   - 入力ファイルのバリデーション（形式・サイズ）
   - トランスクリプトファイルのデコードと検証
   - ジョブ作成とDB保存
   - Supabase Storageへのアップロード

3. api/audio.py
   - POST /api/audio/upload (multipart/form-data)
   - 音声/トランスクリプトの種別判定とバリデーション
   - 入力種別に応じて Celery タスクをキュー投入
   - レスポンス: {job_id, websocket_url}

4. schemas/audio.py
   - AudioUploadResponse スキーマ

5. templates/upload.html
   - ドラッグ&ドロップUI
   - フォーム（タイトル、説明）
   - プログレスバー
   - Tailwind CSSでモダンなデザイン
```

### TASK-007: ジョブ管理API
```
依存: TASK-003, TASK-004
優先度: 高

1. api/jobs.py
   - GET /api/jobs (一覧、ページネーション付き)
   - GET /api/jobs/{id} (詳細)
   - DELETE /api/jobs/{id}
   - POST /api/jobs/{id}/retry

2. services/job_service.py
   - ジョブのCRUD操作
   - ステータス更新
   - ログ記録

3. schemas/job.py
   - JobResponse, JobListResponse スキーマ

4. templates/dashboard.html
   - ジョブ一覧テーブル
   - ステータスバッジ（色分け）
   - 新規作成ボタン
```

### TASK-008: WebSocket進捗通知
```
依存: TASK-005, TASK-007
優先度: 高

1. api/websocket.py
   - WS /ws/jobs/{job_id}
   - JWT認証（クエリパラメータ）
   - 接続管理（ConnectionManager）

2. services/notification_service.py
   - WebSocket経由での通知送信
   - 接続の登録・解除
   - ブロードキャスト機能

3. templates/job_detail.html
   - WebSocket接続のJS実装
   - リアルタイム進捗表示（ステップリスト）
   - プログレスバー
   - 完了時の動画プレビューリンク表示
```

### TASK-009: Whisper文字起こしワーカー
```
依存: TASK-005, TASK-006
優先度: 最高

1. requirements.txtに追加:
   - openai-whisper
   - torch (cpu版)

2. services/transcription_service.py
   - Whisperモデルのロード（設定からモデルサイズを読み込み）
   - 音声ファイルから文字起こし実行
   - タイムスタンプ付きセグメントの抽出
   - 結果をtranscriptionsテーブルに保存

3. workers/transcription_worker.py
   - @celery_app.task(queue='ai', max_retries=3)
   - Supabase Storageから音声ファイルをダウンロード
   - transcription_service.pyを呼び出し
   - 完了後にJobステータスを更新
   - WebSocket通知を送信
   - 次のタスク(diarization)をキューに投入

4. models/transcription.py と対応するマイグレーション

注意: モデルファイルは/app/modelsにキャッシュ。
Dockerボリュームに永続化すること。
```

### TASK-010: Gemini AI分析ワーカー
```
依存: TASK-009
優先度: 最高

1. requirements.txtに追加:
   - google-generativeai

2. prompts/summary_prompt.py
   prompts/analysis_prompt.py  
   prompts/avatar_script_prompt.py
   - プロンプトテンプレートをPython文字列で定義
   - 変数置換のformat()方式

3. services/gemini_service.py
   - Geminiクライアント初期化 (gemini-1.5-flash)
   - analyze_conversation(transcript: str) -> AnalysisResult
     要約(3段階)・テーマ・感情・名言を1回のAPIコールで取得
   - generate_avatar_scripts(analysis: AnalysisResult) -> list[AvatarScript]
     キャラクター別セリフを生成
   - generate_youtube_metadata(analysis: AnalysisResult) -> YouTubeMetadata
   - レート制限対応 (指数バックオフリトライ)

4. workers/analysis_worker.py
   - transcriptionsテーブルからデータを取得
   - gemini_service.pyを呼び出し
   - analysesテーブルに保存
   - avatar_scriptsテーブルに保存
   - WebSocket通知、次タスクをキュー投入

5. models/analysis.py, models/avatar_script.py と対応するマイグレーション
```

### TASK-011: 字幕生成
```
依存: TASK-010
優先度: 高

1. services/subtitle_service.py
   - generate_srt(segments: list) -> str
     SRT形式の字幕文字列を生成
     話者ラベルを含む形式: "[山田] こんにちは..."
   - generate_vtt(segments: list) -> str
     WebVTT形式
   - save_subtitle_to_db(job_id, format, content)

2. 字幕生成はanalysis_workerの中で実行（別ワーカー不要）
   生成後にsubtitlesテーブルに保存

3. api/content.py
   - GET /api/content/{job_id}/transcript
   - GET /api/content/{job_id}/analysis
   - GET /api/content/{job_id}/subtitles?format=srt
   
4. schemas/content.py
   - TranscriptResponse, AnalysisResponse スキーマ
```

### TASK-012: Remotion動画生成
```
依存: TASK-011
優先度: 最高

1. remotion/ ディレクトリの初期設定
   - package.json (remotion, react, typescript)
   - tsconfig.json
   - remotion.config.ts

2. remotion/src/types/video-data.ts
   - VideoData型定義（字幕・アバターセリフ・分析結果を含む）

3. remotion/src/components/ の実装
   - Avatar.tsx: アバター画像表示、シンプルな跳ねるアニメーション
   - SubtitleOverlay.tsx: 画面下部に字幕表示
   - Background.tsx: グラデーション背景
   - SpeakerCard.tsx: 右下に話者名表示

4. remotion/src/compositions/AvatarVideo.tsx
   - props: VideoData
   - アバターセリフを時系列に表示
   - 各セリフの区切りで字幕と連動

5. backend/services/video_service.py
   - JSONファイルにVideoDataを出力
   - Node.js subprocess でremotion renderコマンドを実行
     `npx remotion render AvatarVideo output.mp4 --props=data.json`
   - 出力MP4をSupabase Storageにアップロード

6. workers/video_worker.py
   - video_service.pyを呼び出し
   - サムネイル生成（FFmpegで先頭フレーム抽出）
   - WebSocket通知
   - videosテーブルに保存

7. models/video.py と対応するマイグレーション
```

### TASK-013: YouTube投稿
```
依存: TASK-012
優先度: 最高

1. requirements.txtに追加:
   - google-api-python-client
   - google-auth-httplib2
   - google-auth-oauthlib

2. services/youtube_service.py
   - get_auth_url() -> str
   - handle_callback(code: str) -> Credentials
   - upload_video(video_path, title, description, tags, privacy) -> str(video_id)
   - upload_thumbnail(video_id, thumbnail_path)
   - refresh_token保存（users.youtube_refresh_tokenに暗号化して保存）

3. api/youtube.py
   - GET /api/youtube/auth-url
   - GET /api/youtube/callback
   - POST /api/youtube/publish
   - GET /api/youtube/publications/{job_id}

4. workers/youtube_worker.py
   - Supabase Storageから動画ダウンロード
   - youtube_service.pyで投稿
   - youtube_publicationsテーブルに保存
   - WebSocket通知（完了）

5. templates/publish.html
   - タイトル・説明・タグの確認・編集フォーム
   - 公開設定の選択
   - 投稿ボタン
   - 完了後にYouTube URLを表示

6. models/youtube_publication.py と対応するマイグレーション
```

---

## Phase 2: 品質向上

### TASK-014: 話者分離（pyannote）
```
依存: TASK-009
優先度: 中

1. requirements.txtに追加:
   - pyannote.audio
   - torch (cpu版)
   ※ Hugging Face のトークンが必要（無料）

2. services/diarization_service.py
   - pyannoteパイプラインのロード
   - 音声から話者セグメントを抽出
   - 文字起こしセグメントとの時系列マージ

3. workers/diarization_worker.py
   - transcription_workerとanalysis_workerの間に挿入
   - speaker_segmentsテーブルに保存

4. 話者名の編集UI（templates/job_detail.html に追加）
   - SPEAKER_00 → 「山田」のような名前設定
   - API: PATCH /api/jobs/{id}/speakers
```

### TASK-015: Shorts動画生成
```
依存: TASK-012
優先度: 中

1. remotion/src/compositions/ShortsVideo.tsx
   - 縦型（1080x1920）レイアウト
   - 名言カードを中央に大きく表示
   - 背景アニメーション

2. services/shorts_service.py
   - analysesからquotesを取得
   - 最良の名言を選択（スコアリング）
   - Remotionで60秒以内の縦型動画生成
   - #Shortsタグを含むメタデータ生成

3. workers/video_worker.pyにShorts生成を追加

4. YouTube投稿時のShorts対応
   - 動画名に「#Shorts」を含める
   -縦型動画として投稿
```

---

## UI/UX タスク

### TASK-UI-001: ベーステンプレート
```
templates/base.html を作成:
- Tailwind CSS CDN
- ナビゲーションバー（ロゴ、メニュー、ユーザーアイコン）
- フラッシュメッセージ（エラー・成功通知）
- フッター
- モバイル対応（レスポンシブ）
- カラーテーマ: 紫〜青グラデーション
```

### TASK-UI-002: ダッシュボード画面
```
templates/dashboard.html を作成:
- ジョブ一覧カード形式
- 各カードに: タイトル、ステータスバッジ、作成日、YouTube URL（あれば）
- 「新しい動画を作成」ボタン（右上、プライマリカラー）
- ローディング状態・空状態の表示
- ページネーション
- Tailwind CSSでかわいいデザイン
```

### TASK-UI-003: 動画プレビュー画面
```
templates/job_preview.html を作成:
- 動画プレイヤー（video要素、controls付き）
- 右側に分析結果パネル
  - 要約（タブで3段階切り替え）
  - テーマ・キーワードタグ
  - 名言カード
- 下部に字幕表示
- 「YouTube投稿へ進む」ボタン
- 「動画をダウンロード」ボタン
```

---

## テストタスク

### TASK-TEST-001: サービス単体テスト
```
tests/unit/ に以下を作成:

1. test_subtitle_service.py
   - SRT生成のテスト（入力セグメント → 期待SRT文字列）
   - VTT生成のテスト
   - 話者ラベル付き字幕のテスト

2. test_gemini_service.py
   - モックを使ったAPI呼び出しテスト
   - プロンプト生成のテスト
   - レスポンスパースのテスト

3. test_audio_service.py
   - ファイルバリデーションのテスト
   - 各形式のテスト
```

### TASK-TEST-002: API統合テスト
```
tests/integration/ に以下を作成:
- test_audio_api.py: アップロードAPIのテスト
- test_jobs_api.py: ジョブCRUDのテスト
- 認証テスト（モックJWT）
- conftest.pyでテスト用DBセットアップ
```

---

## 運用タスク

### TASK-OPS-001: ヘルスチェック・監視
```
1. GET /health エンドポイントの実装
   - DB接続確認
   - Redis接続確認
   - Supabase接続確認
   - レスポンス: {status, services, version, timestamp}

2. Flower設定のカスタマイズ
   - ベーシック認証を追加

3. docker-compose.ymlにヘルスチェック設定を追加
```

### TASK-OPS-002: 本番環境設定
```
1. docker-compose.prod.yml を作成
   - nginx設定（SSL対応）
   - 環境変数をsecrets管理
   - ログ設定（JSONログ）
   - リスタートポリシー

2. nginx/nginx.conf を作成
   - リバースプロキシ設定
   - gzip圧縮
   - 静的ファイルのキャッシュ

3. scripts/deploy.sh を作成
   - git pull
   - docker compose pull
   - docker compose up -d
   - alembic upgrade head
```

---

## タスク依存関係グラフ

```
TASK-001 (セットアップ)
    └── TASK-002 (FastAPI基盤)
            ├── TASK-003 (DB設定)
            │       ├── TASK-004 (認証)
            │       └── TASK-006 (アップロード)
            │               └── TASK-007 (ジョブ管理)
            │                       └── TASK-008 (WebSocket)
            └── TASK-005 (Celery)
                    └── TASK-009 (Whisper)
                            └── [TASK-014 話者分離] (Phase 2)
                            └── TASK-010 (Gemini分析)
                                    └── TASK-011 (字幕生成)
                                            └── TASK-012 (動画生成)
                                                    ├── [TASK-015 Shorts] (Phase 2)
                                                    └── TASK-013 (YouTube投稿)
```

---

*文書終端*
