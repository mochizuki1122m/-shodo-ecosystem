.PHONY: help setup build up down logs clean test

# デフォルトターゲット
help:
	@echo "Shodo Ecosystem - Makefile Commands"
	@echo ""
	@echo "Usage: make [command]"
	@echo ""
	@echo "Commands:"
	@echo "  setup     - 初期セットアップ（依存関係のインストール）"
	@echo "  build     - Dockerイメージのビルド"
	@echo "  up        - サービスの起動"
	@echo "  down      - サービスの停止"
	@echo "  logs      - ログの表示"
	@echo "  clean     - クリーンアップ"
	@echo "  test      - テストの実行"
	@echo "  dev       - 開発環境の起動（ホットリロード有効）"

# 初期セットアップ
setup:
	@echo "🚀 Setting up Shodo Ecosystem..."
	@echo "Creating necessary directories..."
	@mkdir -p models cache browser-data
	@echo "Creating environment file..."
	@cp -n .env.example .env || true
	@echo "✅ Setup complete!"

# Dockerイメージのビルド
build:
	@echo "🔨 Building Docker images..."
	docker-compose build --parallel

# サービスの起動
up:
	@echo "🚀 Starting services..."
	docker-compose up -d
	@echo "✅ Services started!"
	@echo ""
	@echo "Access points:"
	@echo "  Frontend:    http://localhost:3000"
	@echo "  Backend API: http://localhost:8000"
	@echo "  vLLM Server: http://localhost:8001"
	@echo "  Database:    localhost:5432"
	@echo "  Redis:       localhost:6379"

# 開発環境の起動（ホットリロード有効）
dev:
	@echo "🚀 Starting development environment..."
	docker-compose up

# サービスの停止
down:
	@echo "🛑 Stopping services..."
	docker-compose down

# ログの表示
logs:
	docker-compose logs -f

# 特定サービスのログ
logs-backend:
	docker-compose logs -f backend

logs-frontend:
	docker-compose logs -f frontend

logs-vllm:
	docker-compose logs -f vllm

# クリーンアップ
clean:
	@echo "🧹 Cleaning up..."
	docker-compose down -v
	rm -rf node_modules
	rm -rf frontend/node_modules
	rm -rf backend/__pycache__
	rm -rf .pytest_cache
	@echo "✅ Cleanup complete!"

# テストの実行
test:
	@echo "🧪 Running tests..."
	@echo "Backend tests..."
	docker-compose run --rm backend pytest
	@echo "Frontend tests..."
	docker-compose run --rm frontend npm test

# データベースのマイグレーション
migrate:
	docker-compose exec backend python -m alembic upgrade head

# データベースのシード
seed:
	docker-compose exec backend python scripts/seed_data.py

# 本番用ビルド
build-prod:
	@echo "📦 Building for production..."
	docker-compose -f docker-compose.prod.yml build

# 本番環境のデプロイ
deploy:
	@echo "🚀 Deploying to production..."
	docker-compose -f docker-compose.prod.yml up -d

# ヘルスチェック
health:
	@echo "🏥 Health check..."
	@curl -s http://localhost:8000/health | jq '.' || echo "Backend not responding"
	@curl -s http://localhost:8001/health | jq '.' || echo "vLLM not responding"

# パフォーマンステスト
perf:
	@echo "⚡ Performance test..."
	@ab -n 100 -c 10 http://localhost:8000/api/v1/nlp/analyze