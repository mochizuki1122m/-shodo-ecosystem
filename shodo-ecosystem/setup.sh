#!/bin/bash

set -e

echo "╔════════════════════════════════════════╗"
echo "║     Shodo Ecosystem Setup Script       ║"
echo "╚════════════════════════════════════════╝"
echo ""

# 色付き出力
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# asdfのインストール確認
check_asdf() {
    echo -e "${YELLOW}Checking asdf...${NC}"
    if ! command -v asdf &> /dev/null; then
        echo -e "${YELLOW}Installing asdf...${NC}"
        git clone https://github.com/asdf-vm/asdf.git ~/.asdf --branch v0.13.1
        echo '. "$HOME/.asdf/asdf.sh"' >> ~/.bashrc
        echo '. "$HOME/.asdf/completions/asdf.bash"' >> ~/.bashrc
        source ~/.asdf/asdf.sh
    fi
    echo -e "${GREEN}✓ asdf is installed${NC}"
}

# asdfプラグインのインストール
install_asdf_plugins() {
    echo -e "${YELLOW}Installing asdf plugins...${NC}"
    
    asdf plugin add nodejs https://github.com/asdf-vm/asdf-nodejs.git || true
    asdf plugin add python https://github.com/danhper/asdf-python.git || true
    asdf plugin add postgres https://github.com/smashedtoatoms/asdf-postgres.git || true
    asdf plugin add redis https://github.com/smashedtoatoms/asdf-redis.git || true
    
    echo -e "${GREEN}✓ asdf plugins installed${NC}"
}

# 依存関係のインストール
install_dependencies() {
    echo -e "${YELLOW}Installing dependencies from .tool-versions...${NC}"
    asdf install
    echo -e "${GREEN}✓ Dependencies installed${NC}"
}

# pnpmのインストール
install_pnpm() {
    echo -e "${YELLOW}Installing pnpm...${NC}"
    if ! command -v pnpm &> /dev/null; then
        npm install -g pnpm@8.14.1
    fi
    echo -e "${GREEN}✓ pnpm installed${NC}"
}

# Ollamaのインストール
install_ollama() {
    echo -e "${YELLOW}Checking Ollama...${NC}"
    if ! command -v ollama &> /dev/null; then
        echo -e "${YELLOW}Installing Ollama...${NC}"
        curl -fsSL https://ollama.ai/install.sh | sh
    fi
    echo -e "${GREEN}✓ Ollama installed${NC}"
    
    # Ollamaサービスの起動
    echo -e "${YELLOW}Starting Ollama service...${NC}"
    ollama serve &> /dev/null &
    sleep 5
    
    # モデルのダウンロード
    echo -e "${YELLOW}Pulling Llama2 model (this may take a while)...${NC}"
    ollama pull llama2:7b-chat
    echo -e "${GREEN}✓ Llama2 model ready${NC}"
}

# PostgreSQLのセットアップ
setup_postgres() {
    echo -e "${YELLOW}Setting up PostgreSQL...${NC}"
    
    # データベースクラスタの初期化
    if [ ! -d "$HOME/.asdf/installs/postgres/15.5/data" ]; then
        initdb -D ~/.asdf/installs/postgres/15.5/data
    fi
    
    # PostgreSQLの起動
    pg_ctl start -D ~/.asdf/installs/postgres/15.5/data -l /tmp/postgres.log || true
    sleep 3
    
    # データベースとユーザーの作成
    createuser -s shodo || true
    createdb shodo || true
    
    echo -e "${GREEN}✓ PostgreSQL setup complete${NC}"
}

# Redisのセットアップ
setup_redis() {
    echo -e "${YELLOW}Starting Redis...${NC}"
    redis-server --daemonize yes
    echo -e "${GREEN}✓ Redis started${NC}"
}

# Node.js依存関係のインストール
install_node_deps() {
    echo -e "${YELLOW}Installing Node.js dependencies...${NC}"
    pnpm install
    echo -e "${GREEN}✓ Node.js dependencies installed${NC}"
}

# 環境変数ファイルの作成
create_env_file() {
    if [ ! -f .env ]; then
        echo -e "${YELLOW}Creating .env file...${NC}"
        cat > .env << EOF
# Shodo Ecosystem Environment Variables

# Node環境
NODE_ENV=development

# サーバーポート
BACKEND_PORT=8000
FRONTEND_PORT=3000
AI_PORT=8001

# データベース
DATABASE_URL=postgresql://shodo@localhost:5432/shodo
REDIS_URL=redis://localhost:6379

# AI設定
INFERENCE_ENGINE=ollama
MODEL_NAME=llama2:7b-chat
OLLAMA_HOST=http://localhost:11434

# セキュリティ
JWT_SECRET=change-this-in-production-$(openssl rand -hex 32)

# ログ
LOG_LEVEL=info
EOF
        echo -e "${GREEN}✓ .env file created${NC}"
    else
        echo -e "${YELLOW}.env file already exists${NC}"
    fi
}

# PM2のインストール
install_pm2() {
    echo -e "${YELLOW}Installing PM2...${NC}"
    if ! command -v pm2 &> /dev/null; then
        pnpm add -g pm2
    fi
    echo -e "${GREEN}✓ PM2 installed${NC}"
}

# メイン処理
main() {
    echo -e "${YELLOW}Starting setup...${NC}"
    echo ""
    
    # OSの確認
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo -e "${GREEN}Detected macOS${NC}"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo -e "${GREEN}Detected Linux${NC}"
    else
        echo -e "${RED}Unsupported OS: $OSTYPE${NC}"
        exit 1
    fi
    
    # セットアップ実行
    check_asdf
    install_asdf_plugins
    install_dependencies
    install_pnpm
    install_ollama
    setup_postgres
    setup_redis
    install_node_deps
    create_env_file
    install_pm2
    
    echo ""
    echo "╔════════════════════════════════════════╗"
    echo "║     Setup Complete! 🎉                 ║"
    echo "╚════════════════════════════════════════╝"
    echo ""
    echo "To start the development server:"
    echo "  ${GREEN}pnpm dev${NC}"
    echo ""
    echo "To start with PM2 (production):"
    echo "  ${GREEN}pnpm start${NC}"
    echo ""
    echo "To migrate to vLLM later:"
    echo "  ${GREEN}pnpm run setup:vllm${NC}"
    echo "  ${GREEN}INFERENCE_ENGINE=vllm pnpm dev${NC}"
    echo ""
}

# エラーハンドリング
trap 'echo -e "${RED}Setup failed!${NC}"; exit 1' ERR

# 実行
main