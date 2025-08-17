#!/bin/bash

# ========================================
# Shodo Ecosystem Production Deployment Script
# ========================================

set -e  # エラーで停止
set -u  # 未定義変数でエラー

# カラー出力
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ログ関数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# バナー表示
show_banner() {
    cat << "EOF"
    ╔═══════════════════════════════════════╗
    ║     Shodo Ecosystem Deployment        ║
    ║         Production v1.0.0              ║
    ╚═══════════════════════════════════════╝
EOF
}

# 環境選択
select_environment() {
    echo ""
    echo "デプロイ環境を選択してください:"
    echo "1) Production (本番環境)"
    echo "2) Staging (ステージング環境)"
    echo "3) Development (開発環境)"
    read -p "選択 [1-3]: " env_choice
    
    case $env_choice in
        1)
            ENVIRONMENT="production"
            ENV_FILE=".env.production"
            COMPOSE_FILE="docker-compose.production.yml"
            ;;
        2)
            ENVIRONMENT="staging"
            ENV_FILE=".env.staging"
            COMPOSE_FILE="docker-compose.staging.yml"
            ;;
        3)
            ENVIRONMENT="development"
            ENV_FILE=".env"
            COMPOSE_FILE="docker-compose.yml"
            ;;
        *)
            log_error "無効な選択です"
            exit 1
            ;;
    esac
    
    log_info "環境: $ENVIRONMENT"
}

# 前提条件チェック
check_prerequisites() {
    log_info "前提条件をチェック中..."
    
    # Docker確認
    if ! command -v docker &> /dev/null; then
        log_error "Dockerがインストールされていません"
        exit 1
    fi
    
    # Docker Compose確認
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Composeがインストールされていません"
        exit 1
    fi
    
    # Git確認
    if ! command -v git &> /dev/null; then
        log_error "Gitがインストールされていません"
        exit 1
    fi
    
    # 環境変数ファイル確認
    if [ ! -f "$ENV_FILE" ]; then
        log_error "環境変数ファイル $ENV_FILE が見つかりません"
        log_info "cp .env.example $ENV_FILE を実行して設定してください"
        exit 1
    fi
    
    log_success "前提条件チェック完了"
}

# 環境変数検証
validate_env_vars() {
    log_info "環境変数を検証中..."
    
    source $ENV_FILE
    
    # 必須環境変数チェック
    required_vars=(
        "POSTGRES_PASSWORD"
        "REDIS_PASSWORD"
        "JWT_SECRET_KEY"
        "ENCRYPTION_KEY"
    )
    
    missing_vars=()
    for var in "${required_vars[@]}"; do
        if [ -z "${!var:-}" ] || [[ "${!var}" == *"CHANGE_ME"* ]]; then
            missing_vars+=($var)
        fi
    done
    
    if [ ${#missing_vars[@]} -gt 0 ]; then
        log_error "以下の環境変数が設定されていません:"
        printf '%s\n' "${missing_vars[@]}"
        exit 1
    fi
    
    log_success "環境変数検証完了"
}

# Gitリポジトリ更新
update_repository() {
    log_info "リポジトリを更新中..."
    
    # 現在のブランチ確認
    current_branch=$(git branch --show-current)
    log_info "現在のブランチ: $current_branch"
    
    # 変更確認
    if [ -n "$(git status --porcelain)" ]; then
        log_warning "未コミットの変更があります"
        read -p "続行しますか？ (y/n): " continue_choice
        if [ "$continue_choice" != "y" ]; then
            exit 1
        fi
    fi
    
    # 最新を取得
    if [ "$ENVIRONMENT" == "production" ]; then
        git fetch origin main
        log_info "mainブランチの最新を取得しました"
    fi
    
    log_success "リポジトリ更新完了"
}

# Dockerイメージビルド
build_images() {
    log_info "Dockerイメージをビルド中..."
    
    docker-compose -f $COMPOSE_FILE build --no-cache
    
    log_success "イメージビルド完了"
}

# データベースマイグレーション
run_migrations() {
    log_info "データベースマイグレーションを実行中..."
    
    # PostgreSQLが起動するまで待機
    docker-compose -f $COMPOSE_FILE up -d postgres
    sleep 10
    
    # マイグレーション実行
    docker-compose -f $COMPOSE_FILE run --rm backend alembic upgrade head
    
    log_success "マイグレーション完了"
}

# ヘルスチェック
health_check() {
    log_info "ヘルスチェックを実行中..."
    
    services=("backend" "frontend" "ai-server" "postgres" "redis")
    max_retries=30
    
    for service in "${services[@]}"; do
        log_info "$service のヘルスチェック中..."
        retries=0
        
        while [ $retries -lt $max_retries ]; do
            if docker-compose -f $COMPOSE_FILE ps | grep -q "$service.*healthy"; then
                log_success "$service は正常です"
                break
            fi
            
            retries=$((retries + 1))
            if [ $retries -eq $max_retries ]; then
                log_error "$service のヘルスチェックに失敗しました"
                return 1
            fi
            
            sleep 2
        done
    done
    
    log_success "全サービスのヘルスチェック完了"
}

# サービス起動
start_services() {
    log_info "サービスを起動中..."
    
    # 既存のコンテナを停止
    docker-compose -f $COMPOSE_FILE down
    
    # サービス起動
    docker-compose -f $COMPOSE_FILE up -d
    
    # ヘルスチェック
    sleep 10
    health_check
    
    log_success "サービス起動完了"
}

# SSL証明書セットアップ
setup_ssl() {
    if [ "$ENVIRONMENT" == "production" ]; then
        log_info "SSL証明書をセットアップ中..."
        
        # Let's Encrypt証明書取得（certbot使用）
        if command -v certbot &> /dev/null; then
            certbot certonly --standalone \
                -d shodo-ecosystem.com \
                -d www.shodo-ecosystem.com \
                -d api.shodo-ecosystem.com \
                --non-interactive \
                --agree-tos \
                --email admin@shodo-ecosystem.com
            
            log_success "SSL証明書セットアップ完了"
        else
            log_warning "certbotがインストールされていません。SSL設定をスキップします"
        fi
    fi
}

# バックアップ作成
create_backup() {
    log_info "バックアップを作成中..."
    
    timestamp=$(date +%Y%m%d_%H%M%S)
    backup_dir="backups/$timestamp"
    mkdir -p $backup_dir
    
    # データベースバックアップ
    docker-compose -f $COMPOSE_FILE exec -T postgres \
        pg_dump -U shodo shodo > "$backup_dir/database.sql"
    
    # 設定ファイルバックアップ
    cp $ENV_FILE "$backup_dir/"
    cp $COMPOSE_FILE "$backup_dir/"
    
    # 圧縮
    tar -czf "backups/backup_$timestamp.tar.gz" -C backups $timestamp
    rm -rf "$backup_dir"
    
    log_success "バックアップ作成完了: backups/backup_$timestamp.tar.gz"
}

# モニタリング設定
setup_monitoring() {
    if [ "$ENVIRONMENT" == "production" ]; then
        log_info "モニタリングを設定中..."
        
        # Prometheus起動
        docker-compose -f $COMPOSE_FILE up -d prometheus
        
        # Grafana起動
        docker-compose -f $COMPOSE_FILE up -d grafana
        
        # Loki起動
        docker-compose -f $COMPOSE_FILE up -d loki promtail
        
        log_success "モニタリング設定完了"
        log_info "Grafana: http://localhost:3001 (admin/設定したパスワード)"
        log_info "Prometheus: http://localhost:9090"
    fi
}

# デプロイ後のテスト
post_deployment_test() {
    log_info "デプロイ後のテストを実行中..."
    
    # APIヘルスチェック
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        log_success "APIサーバー: OK"
    else
        log_error "APIサーバー: NG"
    fi
    
    # フロントエンドチェック
    if curl -f http://localhost:3000 > /dev/null 2>&1; then
        log_success "フロントエンド: OK"
    else
        log_error "フロントエンド: NG"
    fi
    
    # AIサーバーチェック
    if curl -f http://localhost:8001/health > /dev/null 2>&1; then
        log_success "AIサーバー: OK"
    else
        log_warning "AIサーバー: 起動中の可能性があります"
    fi
    
    log_success "デプロイ後テスト完了"
}

# ロールバック
rollback() {
    log_warning "デプロイをロールバック中..."
    
    # 最新のバックアップを探す
    latest_backup=$(ls -t backups/backup_*.tar.gz 2>/dev/null | head -1)
    
    if [ -z "$latest_backup" ]; then
        log_error "バックアップが見つかりません"
        exit 1
    fi
    
    log_info "バックアップを復元: $latest_backup"
    
    # サービス停止
    docker-compose -f $COMPOSE_FILE down
    
    # バックアップ展開
    tar -xzf "$latest_backup" -C /tmp
    
    # データベース復元
    docker-compose -f $COMPOSE_FILE up -d postgres
    sleep 10
    docker-compose -f $COMPOSE_FILE exec -T postgres \
        psql -U shodo shodo < /tmp/*/database.sql
    
    # サービス再起動
    docker-compose -f $COMPOSE_FILE up -d
    
    log_success "ロールバック完了"
}

# クリーンアップ
cleanup() {
    log_info "クリーンアップ中..."
    
    # 未使用のDockerリソース削除
    docker system prune -f
    
    # 古いバックアップ削除（30日以上）
    find backups -name "backup_*.tar.gz" -mtime +30 -delete 2>/dev/null || true
    
    log_success "クリーンアップ完了"
}

# メイン処理
main() {
    show_banner
    
    # コマンドライン引数処理
    case "${1:-}" in
        rollback)
            rollback
            exit 0
            ;;
        backup)
            create_backup
            exit 0
            ;;
        health)
            health_check
            exit 0
            ;;
        cleanup)
            cleanup
            exit 0
            ;;
    esac
    
    # デプロイ実行
    select_environment
    check_prerequisites
    validate_env_vars
    
    log_info "デプロイを開始します"
    read -p "続行しますか？ (y/n): " deploy_choice
    if [ "$deploy_choice" != "y" ]; then
        log_info "デプロイをキャンセルしました"
        exit 0
    fi
    
    # バックアップ作成
    if [ "$ENVIRONMENT" == "production" ]; then
        create_backup
    fi
    
    update_repository
    build_images
    run_migrations
    start_services
    
    if [ "$ENVIRONMENT" == "production" ]; then
        setup_ssl
        setup_monitoring
    fi
    
    post_deployment_test
    cleanup
    
    log_success "========================================="
    log_success "デプロイが正常に完了しました！"
    log_success "========================================="
    log_info "アプリケーション: http://localhost:3000"
    log_info "API: http://localhost:8000"
    log_info "API ドキュメント: http://localhost:8000/docs"
    
    if [ "$ENVIRONMENT" == "production" ]; then
        log_info "Flower (Celery): http://localhost:5555"
        log_info "Grafana: http://localhost:3001"
        log_info "Prometheus: http://localhost:9090"
    fi
}

# エラーハンドリング
trap 'log_error "エラーが発生しました。ロールバックするには ./deploy.sh rollback を実行してください"' ERR

# スクリプト実行
main "$@"