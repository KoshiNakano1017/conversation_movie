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
 ③ Remotion          会議室スタイルで動画レンダリング（参加者全員アバター・発言者ハイライト）
        ▼
 ④ TTS 音声合成       edge-tts で参加者ごとに異なる声を割り当て
        ▼
 ⑤ FFmpeg 合成        字幕焼き込み・音声ミックス・サムネイル抽出
        ▼
   完成動画（MP4）＋ サムネイル
```

進捗は **WebSocket** でリアルタイムに通知されます。

---

## 🛠 技術スタック

| 領域 | 採用技術 |
| --- | --- |
| バックエンド | Python / FastAPI |
| 非同期処理 | Celery + Redis（Upstash） |
| DB | SQLAlchemy + PostgreSQL（Supabase） |
| AI 分析 | Google Gemini |
| 文字起こし | OpenAI Whisper |
| 動画生成 | Remotion（React / TypeScript） |
| 音声合成（TTS） | Microsoft Edge TTS（edge-tts） |
| メディア処理 | FFmpeg（字幕焼き込み・音声ミックス・サムネイル） |
| リアルタイム通知 | WebSocket + Redis Pub/Sub |

---

## 🚀 運用方法

### 必要なもの
- Python 3.12 / Node.js（Remotion 用）/ FFmpeg
- Supabase（PostgreSQL）, Upstash（Redis）, Gemini API キー

### セットアップ
```bash
# 1. 環境変数を用意（.env.example をコピーして値を設定）
cp .env.example .env

# 2. バックエンド依存をインストール
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt -r requirements-dev.txt

# 3. Remotion 依存をインストール
cd ../remotion
npm install
```

### 起動
```bash
# API サーバー
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Celery ワーカー（別ターミナル）
celery -A app.celery_app worker -Q ai,video -P solo --concurrency=1 --loglevel=info
```

### 動画を作る
```bash
# トランスクリプトを貼り付けて生成開始
curl -X POST http://localhost:8000/api/transcript/paste \
  -H "Content-Type: application/json" \
  -d '{"title":"定例MTG","language":"ja","text":"司会: 本日は... 田中: 了解です..."}'

# ファイルアップロード（音声 or テキスト/字幕）
curl -X POST http://localhost:8000/api/audio/upload \
  -F "file=@transcript.txt" -F "title=定例MTG" -F "language=ja"
```

進捗は `GET /api/jobs/{job_id}` または WebSocket `ws://localhost:8000/ws/jobs/{job_id}` で確認できます。
完成動画は `media/video/{job_id}/` 配下に出力されます。

---

## 💡 工夫したポイント

- **トランスクリプト直接入力に対応** — 音声処理（Whisper）をスキップでき、テキストがあれば高速に動画化できる。
- **会議室スタイルの可視化** — 単なる字幕動画ではなく、参加者全員をアバター化し、発言者をハイライト＆口パクさせることで「誰が何を言ったか」が直感的に分かる。
- **参加者ごとに異なる音声** — TTS の声・話速・ピッチを話者ごとに割り当て、会話として聞き分けられる。
- **疎結合なパイプライン** — Celery chain で「分析 → 字幕 → 動画 → 音声」を段階実行。各ステップが独立して失敗・リトライ可能。
- **DB 互換レイヤー** — PostgreSQL（本番）と SQLite（テスト）の両対応のため、UUID / JSONB / ARRAY をカスタム型で吸収。
- **Windows での外部CLI解決** — FFmpeg / npx の PATH 解決が効かない環境向けに `.env` のフォールバックパスを参照する仕組み。
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
├─ remotion/           Remotion 動画テンプレート（会議室コンポジション）
├─ docs/               要求仕様・設計・運用ドキュメント
└─ media/              生成された動画（Git 管理対象外）
```

---

## ⚠️ 注意

- `.env` には API キーや DB パスワードが含まれるため **Git にはコミットしません**（`.env.example` を参照）。
- Remotion の CPU レンダリングは尺に比例して時間がかかります。高速化にはクラウドレンダリング（Remotion Lambda / Shotstack 等）への移行が選択肢です。

---

## 📌 ステータス

MVP 開発中。トランスクリプト入力 → 会議室スタイル動画（字幕・参加者別TTS付き）の生成まで動作確認済み。
