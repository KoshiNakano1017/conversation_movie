"""新規トランスクリプトを paste してジョブ完了までポーリング"""
import json
import sys
import time

import httpx
from fastapi.testclient import TestClient

sys.path.insert(0, ".")

from app.main import app

PAYLOAD = {
    "title": "新規動作確認 MTG 2026-05-21",
    "language": "ja",
    "description": "paste からの新規トランスクリプト送信テスト",
    "text": (
        "司会: 本日は新しいトランスクリプトの動作確認を行います。"
        "田中: 了解しました。APIの貼り付けエンドポイントからジョブが作成されるか確認します。"
        "鈴木: Geminiによる要約とアバターセリフ生成、その後のRemotion動画レンダリングまで通るか見たいです。"
        "司会: では進めましょう。アクションアイテムは田中さんがワーカーログを確認、鈴木さんがプレビュー画面を確認することです。"
        "鈴木: 承知しました。完了したらジョブ詳細ページで進捗100パーセントになるはずですね。"
        "司会: その通りです。問題があれば共有してください。以上で終了します。"
    ),
}

BASE = "http://localhost:8000"


def main() -> None:
    print("=== POST /api/transcript/paste ===")
    client = TestClient(app)
    r = client.post("/api/transcript/paste", json=PAYLOAD)
    print(f"status: {r.status_code}")
    if r.status_code != 202:
        print(f"body: {r.text[:1000]}")
        sys.exit(1)

    data = r.json()
    job_id = data["job_id"]
    print(f"job_id: {job_id}")
    print(f"character_count: {data.get('character_count')}")
    print(f"preview: {BASE}/jobs/{job_id}/preview")
    print(f"detail:  {BASE}/jobs/{job_id}")

    print("\n=== polling job status (GET /api/jobs/{id}) ===")
    with httpx.Client(timeout=30.0) as http:
        for i in range(120):
            jr = http.get(f"{BASE}/api/jobs/{job_id}")
            if jr.status_code != 200:
                print(f"  [{i}] GET failed: {jr.status_code}")
            else:
                job = jr.json()
                status = job.get("status")
                progress = job.get("progress")
                err = job.get("error_message")
                print(f"  [{i}] status={status} progress={progress}% error={err or '-'}")
                if status in ("completed", "failed", "cancelled"):
                    print("\n=== final ===")
                    print(json.dumps(job, ensure_ascii=False, indent=2, default=str))
                    sys.exit(0 if status == "completed" else 1)
            time.sleep(5)

    print("timeout")
    sys.exit(1)


if __name__ == "__main__":
    main()
