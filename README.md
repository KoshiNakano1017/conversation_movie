# ConversationMovie 🎬

会議の **トランスクリプト（文字起こし）や音声** から、AI が内容を分析・要約し、
**アバターキャラクターが会議室で発言する解説動画** を自動生成するアプリです。

「議事録は読まれない」を解決し、会議のエッセンスを短時間で振り返れる動画コンテンツに変換します。

---

## 🌟 何のためのアプリか

- 長い会議の記録を、**見て分かるダイジェスト動画**に自動変換
- 「誰が」「どんな発言をしたか」を、参加者アバターと発言ハイライトで可視化
- 生成物は YouTube 等での共有を想定（タイトル・概要・タグも AI が提案）

### 想定ユースケース
- 社内ミーティングの要約共有
- ウェビナー / 勉強会のアーカイブ
- 議事録の代替（読む議事録から観る議事録へ）

---

## 🧩 どんなアプリか（全体フロー）

```
入力（3通り）
 ├─ トランスクリプト貼り付け（テキスト）
 ├─ 字幕/テキストファイル（.txt / .md / .srt / .vtt）
 └─ 音声ファイル（.mp3 / .wav / .m4a ...）→ Whisper で文字起こし
        │
        ▼
 ① Gemini 分析       要約（3段階）・テーマ・名言・センチメント・YouTubeメタデータ・アバター台本
        ▼
 ② 字幕生成          発言を話者ターンに分割し SRT / VTT を生成
        ▼
 ③ TTS 音声合成（任意） edge-tts → Supabase Storage（公開 URL）
        ▼
 ④ Shotstack          クラウドでタイムライン動画をレンダリング（タイトル＋発言バブル）
        ▼
   完成動画（MP4 URL）＋ サムネイル（Shotstack CDN）
```

進捗は **WebSocket** でリアルタイムに通知されます。

---

## 🛠 技術スタック

| 領域 | 採用技術 |
| --- | --- |
| バックエンド | Python / FastAPI |
| 非同期処理 | Celery + Redis（Upstash） |
| DB / 認証 | SQLAlchemy + PostgreSQL（Supabase） |
| AI 分析 | Google Gemini |
| 動画生成 | **Shotstack**（クラウドレンダリング API） |
| 音声合成（TTS） | Microsoft Edge TTS（edge-tts、任意） |
| 文字起こし | OpenAI Whisper（音声入力時・将来） |
| リアルタイム通知 | WebSocket + Redis Pub/Sub |
| レガシー | Remotion / FFmpeg（`video_service.py` に残存・未使用） |

---

## 🚀 運用方法

MVP は **Docker なし** で、Windows 上の Python venv とクラウドサービス（Supabase / Upstash / Gemini / Shotstack）で運用します。

### 構成概要

```
[ブラウザ / curl]
      │
      ▼
FastAPI (localhost:8000) ──enqueue──▶ Upstash Redis
      │                                      │
      │                                      ▼
      └──────── Supabase PostgreSQL ◀── Celery Worker
                                              ├─ ai キュー: Gemini 分析
                                              └─ video キュー: TTS → Shotstack
```

| プロセス | 役割 | 必須 |
| --- | --- | --- |
| `uvicorn` | REST API・Web UI・WebSocket | ✅ |
| Celery `ai` キュー | トランスクリプト分析（Gemini） | ✅ |
| Celery `video` キュー | TTS + Shotstack レンダリング | ✅ |
| Flower | タスク監視（任意） | — |

---

### 前提条件

| 項目 | 要件 |
| --- | --- |
| OS | Windows 10/11（macOS / Linux も可） |
| Python | 3.11 以上（3.12 推奨） |
| アカウント | [Supabase](https://supabase.com) / [Upstash](https://upstash.com) / [Google AI Studio](https://aistudio.google.com)（Gemini） / [Shotstack](https://shotstack.io) |

**Shotstack について**

| 環境 | 用途 | 料金 |
| --- | --- | --- |
| `stage` | 開発・テスト（透かしあり） | 無料枠 |
| `production` | 本番・SaaS 提供（透かしなし） | 従量課金 |

---

### 初回セットアップ

#### 1. リポジトリと環境変数

```powershell
cd C:\Users\<user>\Desktop\ConversationMovie
copy .env.example .env
```

`.env`（プロジェクトルート）に最低限以下を設定します。

| 変数 | 説明 |
| --- | --- |
| `DATABASE_URL` | Supabase PostgreSQL 接続文字列 |
| `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` | TTS 音声の公開アップロード用（任意だが推奨） |
| `REDIS_URL` | Upstash Redis（`rediss://...`） |
| `GEMINI_API_KEY` | Gemini 分析 |
| `SHOTSTACK_API_KEY` | [ダッシュボード](https://dashboard.shotstack.io/) の **Stage** キー |
| `SHOTSTACK_ENV` | `stage`（開発）または `production`（本番） |
| `MEDIA_DIR` | ローカルメディア保存先（例: `C:/Users/.../ConversationMovie/media`） |

#### 2. Python 依存関係と DB マイグレーション

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt

# TTS 音声付き動画にする場合（任意）
pip install edge-tts

# Supabase にスキーマを適用
.\.venv\Scripts\alembic.exe upgrade head
```

#### 3. Supabase Storage（TTS 利用時のみ）

Shotstack が TTS 音声を HTTP で取得するため、公開バケットが必要です。

1. Supabase ダッシュボード → **Storage** → **New bucket**
2. 名前: `audio`、**Public** を有効化

未作成でも動画は生成されますが、**字幕のみ（無音）** になります。

#### 4. Shotstack API キー

1. [dashboard.shotstack.io](https://dashboard.shotstack.io/) で登録
2. 右上アカウント → **API Keys** → **Stage** キーをコピー
3. `.env` の `SHOTSTACK_API_KEY` に貼り付け

---

### 日常の起動手順

**3 つの PowerShell ターミナル**でそれぞれ起動します。`.env` を変更した場合は、すべてのプロセスを再起動してください。

```powershell
# ── ターミナル 1: API サーバー ──
cd C:\Users\<user>\Desktop\ConversationMovie\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# ── ターミナル 2: AI キュー（Gemini 分析）──
cd C:\Users\<user>\Desktop\ConversationMovie\backend
.\.venv\Scripts\Activate.ps1
celery -A app.celery_app worker -Q ai -P solo --concurrency=1 --loglevel=info

# ── ターミナル 3: video キュー（Shotstack レンダリング）──
cd C:\Users\<user>\Desktop\ConversationMovie\backend
.\.venv\Scripts\Activate.ps1
celery -A app.celery_app worker -Q video -P solo --concurrency=1 --loglevel=info
```

| URL | 用途 |
| --- | --- |
| http://localhost:8000/paste | トランスクリプト貼り付け UI |
| http://localhost:8000/docs | OpenAPI（Swagger） |
| http://localhost:5555 | Flower（起動時のみ） |

**Flower（任意・監視用）**

```powershell
celery -A app.celery_app flower --port=5555
```

---

### 動画を作る（運用フロー）

#### 方法 A: ブラウザ（推奨）

1. http://localhost:8000/paste を開く
2. タイトル・言語・トランスクリプトを入力して送信
3. ジョブ詳細画面で進捗を確認（WebSocket でリアルタイム更新）

テスト用サンプル: `docs/fixtures/transcript_strategy_and_design_thinking.txt`

#### 方法 B: API（curl）

```powershell
# トランスクリプト貼り付け → 202 Accepted + job_id
curl -X POST http://localhost:8000/api/transcript/paste `
  -H "Content-Type: application/json" `
  -d '{"title":"戦略思考とデザイン思考","language":"ja","text":"田島：本日は..."}'

# ジョブ状態確認
curl http://localhost:8000/api/jobs/{job_id}
```

#### パイプラインの流れ

| 順序 | ステータス | 処理内容 | 目安時間 |
| --- | --- | --- | --- |
| 1 | `ANALYZING` | Gemini で要約・テーマ・名言・台本生成 | 数十秒 |
| 2 | `GENERATING_VIDEO` | TTS（任意）→ Shotstack 送信 → ポーリング | **数分** |
| 3 | `COMPLETED` | `videos.storage_path` に Shotstack の動画 URL を保存 | — |

進捗確認:

- REST: `GET /api/jobs/{job_id}`
- WebSocket: `ws://localhost:8000/ws/jobs/{job_id}`

完了後、動画 URL は DB の `videos` テーブル（`storage_path`）またはジョブ詳細 API から取得できます。Shotstack Stage では透かし付き MP4 が CDN URL で返ります。

---

### 停止・再起動

| 操作 | 手順 |
| --- | --- |
| 停止 | 各ターミナルで `Ctrl+C` |
| 設定変更後 | 3 プロセスすべて再起動（`.env` は起動時に読み込み） |
| DB スキーマ更新 | `.\.venv\Scripts\alembic.exe upgrade head` を実行後、ワーカー再起動 |

---

### トラブルシューティング

| 症状 | 確認・対処 |
| --- | --- |
| `POST /api/transcript/paste` が 500 | API を再起動。別ポートで起動して再現するか確認 |
| ジョブが `FAILED`（Shotstack） | `SHOTSTACK_API_KEY` / `SHOTSTACK_ENV=stage` を確認。Celery ログの `SS00x` エラーコードを参照 |
| 動画はできるが無音 | `pip install edge-tts`、Supabase に `audio` 公開バケットを作成 |
| Celery が動かない | `REDIS_URL`（Upstash の `rediss://`）を確認。ワーカーを `-Q ai` と `-Q video` の**両方**起動 |
| マイグレーションエラー | `DATABASE_URL` が Supabase の Direct 接続か確認 |
| レンダリングが長い | Shotstack クラウド処理のため 5〜12 分かかることがある（ポーリング上限 12 分） |

ログの確認先: 各 Celery ターミナルの標準出力、`jobs` テーブル関連の `job_logs`。

---

### 本番・SaaS 化時の切り替え

| 項目 | 開発（現状） | 本番 |
| --- | --- | --- |
| Shotstack | `SHOTSTACK_ENV=stage` | `SHOTSTACK_ENV=production` + Production キー |
| ホスティング | ローカル uvicorn | Render / Railway / Fly.io 等 |
| ワーカー | ローカル Celery | 同上または専用ワーカー VM |

詳細設計: `docs/04_システム構成図.md`

---

## 💡 工夫したポイント

- **トランスクリプト直接入力に対応** — 音声処理（Whisper）をスキップでき、テキストがあれば高速に動画化できる。
- **会議室スタイルの可視化** — 単なる字幕動画ではなく、参加者全員をアバター化し、発言者をハイライト＆口パクさせることで「誰が何を言ったか」が直感的に分かる。
- **参加者ごとに異なる音声** — TTS の声・話速・ピッチを話者ごとに割り当て、会話として聞き分けられる。
- **疎結合なパイプライン** — Celery chain で「分析 → 動画生成」を段階実行。各ステップが独立して失敗・リトライ可能。
- **Shotstack によるクラウドレンダリング** — ローカルの Remotion / FFmpeg に依存せず、Windows でも安定して動画出力できる。
- **DB 互換レイヤー** — PostgreSQL（本番）と SQLite（テスト）の両対応のため、UUID / JSONB / ARRAY をカスタム型で吸収。
- **リアルタイム進捗** — WebSocket + Redis Pub/Sub でジョブ進捗をフロントに即時反映。

---

## 🔍 類似アプリとの差別化

| 観点 | 一般的なツール | ConversationMovie |
| --- | --- | --- |
| 主目的 | 文字起こし / 字幕付与 | **会議内容の要約 + 動画化** |
| 可視化 | テキスト・字幕のみ | **参加者アバターによる会議劇** |
| アバター | リアル系トーキングヘッド（HeyGen/D-ID等、有料・1人） | **コード描画の複数人アバター（低コスト）** |
| 入力 | 音声中心 | **テキスト / 字幕 / 音声の3経路** |
| 出力 | 字幕ファイル | **MP4 + サムネイル + YouTube メタデータ** |

- 既存の文字起こしサービスが「テキスト化」で止まるのに対し、本アプリは **要約 → 演出 → 動画** まで一気通貫。
- 有料のトーキングヘッド API に依存せず、**自前のアバター描画**で複数参加者を低コストに表現。

---

## 📁 ディレクトリ構成（概要）

```
ConversationMovie/
├─ backend/            FastAPI アプリ・Celery ワーカー・各種サービス
│  ├─ app/
│  │  ├─ api/          エンドポイント（transcript / audio / jobs / websocket ...）
│  │  ├─ services/     Gemini / Whisper / 字幕 / 動画 / TTS / 通知
│  │  ├─ workers/      Celery タスク（分析 / 文字起こし / 動画生成）
│  │  └─ models/       SQLAlchemy モデル
│  └─ tests/           ユニット / API テスト
├─ remotion/           旧 Remotion テンプレート（レガシー・未使用）
├─ docs/               要求仕様・設計・運用ドキュメント
│  └─ fixtures/        テスト用トランスクリプト
└─ media/              ローカル一時ファイル（TTS 音声等・Git 管理対象外）
```

---

## ⚠️ 注意

- `.env` には API キーや DB パスワードが含まれるため **Git にはコミットしません**（`.env.example` を参照）。
- Shotstack **Stage** は透かし付き・無料枠向けです。本番公開時は `SHOTSTACK_ENV=production` と Production キーに切り替えてください。
- 動画の最終ファイルは Shotstack CDN にホストされます。ローカル `MEDIA_DIR` は主に TTS 中間ファイル用です。

---

## 📌 ステータス

MVP 開発中。トランスクリプト入力 → Gemini 分析 → **Shotstack** クラウドレンダリング（参加者別 TTS 任意）まで対応。
