.PHONY: dev dev-bg stop test lint typecheck migrate migrate-new shell logs flower clean help

## ─── 開発環境 ──────────────────────────────────────────────
dev:			## Docker Composeで開発環境を起動（フォアグラウンド）
	docker compose up --build

dev-bg:			## Docker Composeで開発環境をバックグラウンド起動
	docker compose up -d --build

stop:			## 開発環境を停止
	docker compose down

restart:		## APIコンテナのみ再起動
	docker compose restart api

## ─── テスト ─────────────────────────────────────────────────
test:			## 全テストを実行（カバレッジレポート付き）
	docker compose exec api pytest tests/ -v --cov=app --cov-report=term-missing

test-unit:		## ユニットテストのみ実行
	docker compose exec api pytest tests/unit/ -v

test-integration:	## 統合テストのみ実行
	docker compose exec api pytest tests/integration/ -v

## ─── コード品質 ─────────────────────────────────────────────
lint:			## Ruffでコードスタイルチェック
	docker compose exec api ruff check app/ tests/

lint-fix:		## Ruffで自動修正
	docker compose exec api ruff check --fix app/ tests/

typecheck:		## mypyで型チェック
	docker compose exec api mypy app/ --ignore-missing-imports

quality:		## lint + typecheck を一括実行
	make lint && make typecheck

## ─── DB / マイグレーション ───────────────────────────────────
migrate:		## マイグレーションを最新に適用
	docker compose exec api alembic upgrade head

migrate-new:		## 新しいマイグレーションファイルを作成（name=xxx で命名）
	docker compose exec api alembic revision --autogenerate -m "$(name)"

migrate-down:		## 1つ前のマイグレーションに戻す
	docker compose exec api alembic downgrade -1

migrate-history:	## マイグレーション履歴を表示
	docker compose exec api alembic history --verbose

## ─── 開発ツール ─────────────────────────────────────────────
shell:			## APIコンテナのPythonシェルに入る
	docker compose exec api python -m IPython

bash:			## APIコンテナのbashに入る
	docker compose exec api bash

logs:			## 全コンテナのログを表示（フォロー）
	docker compose logs -f api worker-ai worker-video worker-upload

logs-api:		## APIのログのみ表示
	docker compose logs -f api

logs-worker:		## ワーカーのログのみ表示
	docker compose logs -f worker-ai worker-video worker-upload

flower:			## Celery監視ダッシュボードをブラウザで開く
	start http://localhost:5555

## ─── クリーンアップ ──────────────────────────────────────────
clean:			## コンテナ・ボリュームを全削除（データ消去注意）
	docker compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

clean-media:		## mediaディレクトリの一時ファイルを削除
	docker compose exec api find /app/media/temp -type f -delete

## ─── セットアップ ────────────────────────────────────────────
setup:			## 初回セットアップ（.envコピー → ビルド → マイグレーション）
	cp -n .env.example .env || true
	docker compose build
	docker compose up -d redis
	sleep 3
	docker compose up -d api
	sleep 5
	make migrate

help:			## コマンド一覧を表示
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
