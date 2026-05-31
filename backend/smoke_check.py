"""動作確認用: TestClient で /api/transcript/paste を直接呼んで Python 例外を露出させる"""
import sys
import traceback

sys.path.insert(0, ".")

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=True)

payload = {
    "title": "動作確認 MTG 2026-05-21",
    "language": "ja",
    "description": "システム動作確認用のサンプル会話",
    "text": (
        "司会: 今日の議題はConversationMovieの動作確認です。よろしくお願いします。"
        "田中: 了解です。まずはトランスクリプト貼り付けから動画生成までの一連のフローを確認しましょう。"
        "鈴木: 良いですね。Gemini分析が成功するか、Remotion動画が生成されるか確認したいです。"
        "司会: では実行してみましょう。アクションアイテムとしては、田中さんがログを確認し、鈴木さんがUI側を確認します。"
        "鈴木: 承知しました。最終的に動画プレビュー画面で要約と動画が表示されればOKですね。"
        "司会: その通りです。本日はありがとうございました。"
    ),
}

print("=== /health ===")
r = client.get("/health")
print(r.status_code, r.json())

print("\n=== POST /api/transcript/paste ===")
try:
    r = client.post("/api/transcript/paste", json=payload)
    print("status:", r.status_code)
    print("body:", r.text[:2000])
except Exception:
    print("EXCEPTION RAISED:")
    traceback.print_exc()
