FROM python:3.11-slim

WORKDIR /app

# システム依存関係のインストール
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Python依存関係のインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードのコピー
COPY src/ ./src/

# モデルディレクトリの作成
RUN mkdir -p /models /cache

# ポート公開
EXPOSE 8001

# vLLMサーバー起動
CMD ["python", "-m", "src.vllm_server"]