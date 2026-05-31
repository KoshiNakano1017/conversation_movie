"""
テストトランスクリプトでデモ動画生成を実行するスクリプト。
使い方: python run_demo.py
"""
import json
import sys
import time
import urllib.request
import urllib.error

BASE_URL = "http://localhost:8000"

TRANSCRIPT = """山田（プロダクトマネージャー）：皆さん、本日はQ2のプロダクトロードマップについて話し合いたいと思います。先週のユーザーヒアリング結果を共有させてください。

鈴木（エンジニアリード）：お願いします。どんなフィードバックがありましたか？

山田：検索機能の改善要望が一番多く、68%のユーザーが「検索が遅い」と回答しています。次にモバイル対応で、42%がスマホで使いにくいと言っています。

佐藤（デザイナー）：モバイル対応は私も気になっていました。現在のUIはデスクトップ前提なので、根本的な見直しが必要ですね。

鈴木：検索の高速化はElasticsearchを導入すれば解決できます。月15万円ほどかかりますが、予算内に収まります。

田中（CSマネージャー）：追加で、「エラーメッセージが分かりにくい」というサポート問い合わせが増えています。UX改善の一環として対応をお願いしたいです。

山田：分かりました。Q2の優先事項を三つに絞ります。一つ目が検索エンジン最適化、二つ目がモバイルファーストデザイン、三つ目がUXエラーハンドリング改善です。各担当者は来週金曜日までに工数見積もりをお願いします。

鈴木：了解です。Elasticsearchの検証環境を今週中に立ち上げます。

佐藤：モバイルのワイヤーフレームを月曜日にお見せします。

田中：よく出るエラーパターンをリスト化して共有します。

山田：ありがとうございます。次回は来週火曜日の同じ時間に行います。お疲れ様でした。"""


def post_json(url: str, data: dict) -> dict:
    payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_json(url: str) -> dict:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    print("=" * 60)
    print("ConversationMovie デモ実行")
    print("=" * 60)

    # ─── Step 1: ヘルスチェック ───────────────────────────────────
    print("\n[1/4] サーバーのヘルスチェック...")
    try:
        health = get_json(f"{BASE_URL}/health")
        print(f"  ステータス: {health['status']}")
        print(f"  DB: {health['services']['database']}, Redis: {health['services']['redis']}")
    except Exception as e:
        print(f"  ❌ サーバーに接続できません: {e}")
        sys.exit(1)

    # ─── Step 2: トランスクリプト送信 ────────────────────────────
    print("\n[2/4] テストトランスクリプトを送信...")
    try:
        result = post_json(
            f"{BASE_URL}/api/transcript/paste",
            {
                "title": "Q2プロダクトロードマップ定例MTG",
                "text": TRANSCRIPT,
                "language": "ja",
                "description": "検索改善・モバイル対応・UX改善の優先度を決定した週次定例",
            },
        )
        job_id = result["job_id"]
        print(f"  ✅ ジョブ作成: {job_id}")
        print(f"  文字数: {result['character_count']} 文字")
        print(f"  ブラウザで確認: http://localhost:8000/jobs/{job_id}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(f"  ❌ API エラー {e.code}: {body}")
        sys.exit(1)

    # ─── Step 3: 進捗ポーリング ───────────────────────────────────
    print("\n[3/4] パイプライン処理中（最大10分待機）...")
    start = time.time()
    max_wait = 600
    poll_interval = 5

    STATUS_EMOJI = {
        "pending": "⏳",
        "analyzing": "🧠",
        "generating_subtitles": "📝",
        "generating_video": "🎬",
        "completed": "✅",
        "failed": "❌",
        "cancelled": "🚫",
    }

    prev_status = ""
    while time.time() - start < max_wait:
        try:
            job = get_json(f"{BASE_URL}/api/jobs/{job_id}")
            status = job["status"]
            progress = job.get("progress", 0)
            emoji = STATUS_EMOJI.get(status, "🔄")

            if status != prev_status:
                elapsed = int(time.time() - start)
                print(f"  {emoji} [{elapsed:>3}s] {status} ({progress}%)")
                prev_status = status

            if status == "completed":
                print(f"\n  🎉 動画生成完了！")
                break
            elif status == "failed":
                err_msg = job.get("error_message", "不明なエラー")
                print(f"\n  ❌ 処理失敗: {err_msg}")
                break
        except Exception as e:
            print(f"  ⚠️  ポーリングエラー: {e}")

        time.sleep(poll_interval)
    else:
        print(f"\n  ⏰ タイムアウト（{max_wait}秒経過）")

    # ─── Step 4: 結果表示 ─────────────────────────────────────────
    print("\n[4/4] 結果確認...")
    try:
        job = get_json(f"{BASE_URL}/api/jobs/{job_id}")
        print(f"  ジョブID: {job_id}")
        print(f"  ステータス: {job['status']}")
        print(f"  動画あり: {job.get('has_video', False)}")
        print(f"  分析あり: {job.get('has_analysis', False)}")

        if job.get("latest_video_path"):
            print(f"\n  📹 動画URL: http://localhost:8000{job['latest_video_path']}")
            print(f"  🔗 プレビュー: http://localhost:8000/jobs/{job_id}/preview")

        if job["status"] == "failed":
            # 分析結果の確認を試みる
            try:
                analysis = get_json(f"{BASE_URL}/api/content/{job_id}/analysis")
                print(f"\n  分析結果（部分）:")
                print(f"    要約: {analysis['summary_short'][:80]}...")
                print(f"    テーマ: {', '.join(analysis['themes'][:3])}")
            except Exception:
                pass
    except Exception as e:
        print(f"  ⚠️  結果取得エラー: {e}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
