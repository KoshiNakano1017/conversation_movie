# API設計書
## ConversationMovie

**文書バージョン**: 1.0.0  
**作成日**: 2026-05-19  
**Base URL**: `https://api.conversationmovie.local`

**更新メモ（2026-05-23）**: アップロードAPIは音声ファイルに加えて、トランスクリプトファイル（`.txt` / `.md` / `.srt` / `.vtt`）も受け付ける仕様に更新。

---

## 1. API概要

### 1.1 認証方式
- **Bearer Token**: Supabase JWTトークン
- ヘッダー: `Authorization: Bearer {token}`

### 1.2 共通レスポンス形式
```json
{
  "success": true,
  "data": {},
  "error": null
}
```

### 1.3 エラーレスポンス形式
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "E004",
    "message": "Gemini API rate limit exceeded",
    "detail": "Please wait 60 seconds before retrying"
  }
}
```

---

## 2. エンドポイント一覧

### 2.1 認証 `/api/auth`

#### POST /api/auth/google
Google OAuthトークン交換（Supabase Auth経由）

**Request**
```json
{
  "access_token": "google_oauth_token"
}
```

**Response 200**
```json
{
  "success": true,
  "data": {
    "user": {
      "id": "uuid",
      "email": "user@example.com",
      "display_name": "山田 太郎"
    },
    "session": {
      "access_token": "supabase_jwt",
      "refresh_token": "refresh_token",
      "expires_at": 1716123456
    }
  }
}
```

#### POST /api/auth/refresh
トークンリフレッシュ

**Request**
```json
{
  "refresh_token": "refresh_token"
}
```

#### POST /api/auth/logout
ログアウト（トークン無効化）

---

### 2.2 音声アップロード `/api/audio`

#### POST /api/audio/upload
音声ファイルまたはトランスクリプトファイルのアップロードとジョブ作成

**Request** (multipart/form-data)
```
file:        <binary> 音声ファイル or トランスクリプトファイル (必須)
title:       string   会議タイトル (必須)
description: string   説明 (任意)
language:    string   言語コード (デフォルト: "ja")
```

**Response 202 Accepted**
```json
{
  "success": true,
  "data": {
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "pending",
    "audio_file_id": "uuid",
    "estimated_duration_minutes": 15,
    "websocket_url": "/ws/jobs/550e8400-e29b-41d4-a716-446655440000"
  }
}
```

**バリデーション**
- ファイルサイズ: 最大500MB
- 対応形式:
  - 音声: mp3, wav, mp4, m4a, ogg, webm
  - トランスクリプト: txt, md, srt, vtt
- タイトル: 1〜100文字

---

### 2.3 ジョブ管理 `/api/jobs`

#### GET /api/jobs
ジョブ一覧取得

**Query Parameters**
```
page:    int     ページ番号 (デフォルト: 1)
limit:   int     件数 (デフォルト: 20, 最大: 100)
status:  string  フィルター (pending|completed|failed)
```

**Response 200**
```json
{
  "success": true,
  "data": {
    "jobs": [
      {
        "id": "uuid",
        "title": "2026-05-19 定例MTG",
        "status": "completed",
        "progress": 100,
        "created_at": "2026-05-19T11:00:00Z",
        "completed_at": "2026-05-19T11:22:00Z",
        "has_video": true,
        "youtube_url": "https://youtube.com/watch?v=xxx"
      }
    ],
    "total": 42,
    "page": 1,
    "limit": 20
  }
}
```

#### GET /api/jobs/{job_id}
ジョブ詳細取得

**Response 200**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "title": "2026-05-19 定例MTG",
    "status": "analyzing",
    "progress": 55,
    "steps": {
      "upload": "completed",
      "transcription": "completed",
      "diarization": "completed",
      "analysis": "in_progress",
      "subtitle": "pending",
      "video": "pending",
      "youtube": "pending"
    },
    "audio_file": {
      "original_filename": "meeting.mp3",
      "duration_seconds": 3600,
      "file_size_bytes": 52428800
    },
    "created_at": "2026-05-19T11:00:00Z"
  }
}
```

#### DELETE /api/jobs/{job_id}
ジョブとすべての関連データを削除

**Response 200**
```json
{
  "success": true,
  "data": { "deleted": true }
}
```

#### POST /api/jobs/{job_id}/retry
失敗したジョブを再実行

**Response 202**
```json
{
  "success": true,
  "data": {
    "job_id": "uuid",
    "status": "pending",
    "retry_step": "video_generation"
  }
}
```

---

### 2.4 コンテンツ取得 `/api/content`

#### GET /api/content/{job_id}/transcript
文字起こし結果取得

**Response 200**
```json
{
  "success": true,
  "data": {
    "full_text": "こんにちは、今日の会議を始めます...",
    "language": "ja",
    "segments": [
      {
        "id": 0,
        "start": 0.0,
        "end": 5.2,
        "text": "こんにちは、今日の会議を始めます。",
        "speaker": "SPEAKER_00",
        "speaker_name": "山田"
      }
    ],
    "duration_seconds": 3600
  }
}
```

#### GET /api/content/{job_id}/analysis
AI分析結果取得

**Response 200**
```json
{
  "success": true,
  "data": {
    "summary_short": "本日の定例MTGでは、Q2の進捗と新機能の優先順位について議論した。",
    "summary_medium": "Q2の進捗確認では...",
    "summary_detailed": {
      "overview": "...",
      "key_decisions": ["機能AをQ2末までにリリース"],
      "action_items": [
        {"who": "山田", "what": "デザイン修正", "when": "5/26"}
      ],
      "next_steps": ["次回MTGで進捗確認"]
    },
    "themes": ["Q2進捗", "新機能開発", "リリース計画"],
    "keywords": ["MVP", "ユーザーテスト", "デプロイ"],
    "quotes": [
      {
        "speaker": "山田",
        "text": "ユーザーが使いやすいものを作ることが全ての基本です。",
        "timestamp": "00:12:34"
      }
    ],
    "overall_sentiment": "positive",
    "suggested_title": "【会議録】Q2進捗とプロダクト戦略について語ってみた",
    "suggested_tags": ["会議録", "プロダクト開発", "スタートアップ"]
  }
}
```

#### GET /api/content/{job_id}/subtitles
字幕ファイルダウンロード

**Query Parameters**
```
format: string  'srt' | 'vtt' (デフォルト: 'srt')
```

**Response 200** (text/plain)
```
1
00:00:00,000 --> 00:00:05,200
[山田] こんにちは、今日の会議を始めます。

2
00:00:05,500 --> 00:00:10,100
[鈴木] よろしくお願いします。
```

---

### 2.5 動画 `/api/videos`

#### GET /api/videos/{job_id}
生成動画一覧取得

**Response 200**
```json
{
  "success": true,
  "data": {
    "videos": [
      {
        "id": "uuid",
        "type": "full",
        "duration_seconds": 3600,
        "stream_url": "https://storage.supabase.co/.../full.mp4",
        "download_url": "https://storage.supabase.co/.../full.mp4?download=true",
        "thumbnail_url": "https://storage.supabase.co/.../thumbnail.jpg",
        "width": 1920,
        "height": 1080
      },
      {
        "id": "uuid",
        "type": "shorts",
        "duration_seconds": 58,
        "stream_url": "https://storage.supabase.co/.../shorts.mp4",
        "width": 1080,
        "height": 1920
      }
    ]
  }
}
```

---

### 2.6 YouTube投稿 `/api/youtube`

#### GET /api/youtube/auth-url
YouTube OAuth認証URLの取得

**Response 200**
```json
{
  "success": true,
  "data": {
    "auth_url": "https://accounts.google.com/o/oauth2/v2/auth?..."
  }
}
```

#### POST /api/youtube/callback
YouTube OAuth コールバック処理

**Request**
```json
{
  "code": "oauth_code",
  "state": "state_param"
}
```

#### POST /api/youtube/publish
YouTube投稿実行

**Request**
```json
{
  "job_id": "uuid",
  "video_id": "uuid",
  "title": "【会議録】Q2進捗について",
  "description": "本日の定例MTGの会議録動画です。\n\n#会議録 #プロダクト開発",
  "tags": ["会議録", "プロダクト開発"],
  "privacy_status": "unlisted",
  "is_shorts": false,
  "publish_full": true,
  "publish_shorts": true
}
```

**Response 202**
```json
{
  "success": true,
  "data": {
    "task_id": "celery_task_id",
    "status": "queued"
  }
}
```

#### GET /api/youtube/publications/{job_id}
投稿済みYouTube情報取得

**Response 200**
```json
{
  "success": true,
  "data": {
    "publications": [
      {
        "id": "uuid",
        "youtube_video_id": "dQw4w9WgXcQ",
        "youtube_url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
        "title": "【会議録】Q2進捗について",
        "is_shorts": false,
        "privacy_status": "public",
        "published_at": "2026-05-19T12:00:00Z"
      }
    ]
  }
}
```

---

### 2.7 WebSocket `/ws`

#### WS /ws/jobs/{job_id}
ジョブ進捗のリアルタイム通知

**認証**: URLパラメータで `?token={jwt}` を付与

**サーバーから送信されるイベント形式**
```json
{
  "event": "step_completed",
  "data": {
    "step": "transcription",
    "status": "completed",
    "progress": 30,
    "message": "文字起こしが完了しました（3,245文字）",
    "timestamp": "2026-05-19T11:05:00Z"
  }
}
```

**イベント種別**
| event | タイミング |
|---|---|
| `step_started` | 各ステップ開始時 |
| `step_completed` | 各ステップ完了時 |
| `step_failed` | 各ステップ失敗時 |
| `job_completed` | 全ジョブ完了時 |
| `job_failed` | ジョブ全体失敗時 |
| `progress_update` | 進捗更新（%） |

---

### 2.8 ヘルス `/`

#### GET /health
ヘルスチェック

**Response 200**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "services": {
    "database": "ok",
    "redis": "ok",
    "storage": "ok"
  },
  "timestamp": "2026-05-19T11:00:00Z"
}
```

---

## 3. HTTPステータスコード

| コード | 用途 |
|---|---|
| 200 | 成功（GET, DELETE） |
| 201 | 作成成功（POST） |
| 202 | 非同期処理受付（POST for jobs） |
| 400 | リクエスト不正 |
| 401 | 認証エラー |
| 403 | 権限なし |
| 404 | リソース未発見 |
| 413 | ファイルサイズ超過 |
| 422 | バリデーションエラー（FastAPI標準） |
| 429 | レート制限 |
| 500 | サーバーエラー |
| 503 | サービス一時停止 |

---

## 4. レート制限

| エンドポイント | 制限 |
|---|---|
| POST /api/audio/upload | 10件/時間/ユーザー |
| POST /api/youtube/publish | 5件/時間/ユーザー |
| GET 全般 | 100件/分/ユーザー |

---

## 5. FastAPI実装例

```python
# app/api/audio.py

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from app.deps import get_current_user
from app.services.audio_service import AudioService
from app.workers.pipeline import ConversationPipeline

router = APIRouter(prefix="/api/audio", tags=["audio"])

@router.post("/upload", status_code=202)
async def upload_audio(
    file: UploadFile = File(...),
    title: str = Form(..., min_length=1, max_length=100),
    description: str = Form(None),
    language: str = Form("ja"),
    speaker_count: int = Form(None),
    current_user = Depends(get_current_user)
):
    # ファイルバリデーション
    allowed_types = {"audio/mpeg", "audio/wav", "video/mp4", "audio/m4a"}
    if file.content_type not in allowed_types:
        raise HTTPException(400, detail="Unsupported file format")
    
    # サービスに委譲
    audio_service = AudioService()
    job = await audio_service.create_job_and_upload(
        user_id=current_user.id,
        file=file,
        title=title,
        description=description,
        language=language,
        speaker_count=speaker_count
    )
    
    # パイプライン開始
    ConversationPipeline.start(job.id, job.audio_file.storage_path)
    
    return {
        "success": True,
        "data": {
            "job_id": str(job.id),
            "status": "pending",
            "websocket_url": f"/ws/jobs/{job.id}"
        }
    }
```

---

*文書終端*
