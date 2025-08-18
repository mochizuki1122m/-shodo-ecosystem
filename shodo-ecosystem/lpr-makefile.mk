# LPR System Makefile Commands

# LPRシステムのセットアップ
lpr-setup:
	@echo "Setting up LPR system..."
	cd backend && pip install playwright && playwright install chromium
	@cp -n .env.example .env || true
	@echo "LPR setup complete!"

# LPRシステム込みでサービス起動
lpr-up:
	@echo "Starting services with LPR system..."
	docker-compose -f docker-compose.yml -f docker-compose.lpr.yml up -d
	@echo "Services with LPR started!"

# LPRシステムの停止
lpr-down:
	@echo "Stopping LPR services..."
	docker-compose -f docker-compose.yml -f docker-compose.lpr.yml down

# LPRシステムのテスト
lpr-test:
	@echo "Running LPR system tests..."
	cd backend && python -m pytest tests/test_lpr_system.py -v