# 🚀 Shodo Ecosystem - Dockerレス環境構築ガイド

**Ollama（最短起動） → vLLM（高性能）への段階的移行パス**

## 📋 概要

Dockerを使わず、ネイティブ環境で直接実行する軽量構成です。
- **開発**: `pnpm dev` で全サービス一括起動
- **本番**: PM2/systemdで安定運用
- **再現性**: asdf + pnpm lockfileで完全保証

## 🎯 アーキテクチャ

```
開発環境:
  Ollama (7B) + pnpm dev → 5分で起動可能

本番環境（段階的移行）:
  Step 1: Ollama + PM2
  Step 2: vLLM + PM2
  Step 3: vLLM + systemd
```

## 🛠️ クイックスタート

### 1. 自動セットアップ（推奨）

```bash
# リポジトリクローン
git clone https://github.com/your-org/shodo-ecosystem.git
cd shodo-ecosystem

# 実行権限付与
chmod +x setup.sh

# 自動セットアップ（10-15分）
./setup.sh

# 開発サーバー起動
pnpm dev
```

これで http://localhost:3000 にアクセス可能！

### 2. 手動セットアップ

#### asdfのインストール

```bash
# asdfインストール
git clone https://github.com/asdf-vm/asdf.git ~/.asdf --branch v0.13.1
echo '. "$HOME/.asdf/asdf.sh"' >> ~/.bashrc
source ~/.bashrc

# プラグイン追加
asdf plugin add nodejs
asdf plugin add python
asdf plugin add postgres
asdf plugin add redis

# ツールインストール
asdf install
```

#### Ollamaのインストール

```bash
# Linux/Mac
curl -fsSL https://ollama.ai/install.sh | sh

# Windows (WSL2)
# OllamaのWindows版をインストール後、WSL2から接続

# モデルダウンロード（4GB程度）
ollama pull llama2:7b-chat
```

#### 依存関係インストール

```bash
# pnpmインストール
npm install -g pnpm@8.14.1

# Node.js依存関係
pnpm install

# 環境変数設定
cp .env.example .env
```

#### データベース起動

```bash
# PostgreSQL初期化
initdb -D ~/.asdf/installs/postgres/15.5/data
pg_ctl start -D ~/.asdf/installs/postgres/15.5/data
createdb shodo

# Redis起動
redis-server --daemonize yes
```

## 🚀 起動方法

### 開発環境（最速）

```bash
# 全サービス一括起動
pnpm dev

# 個別起動
pnpm dev:backend   # バックエンド
pnpm dev:frontend  # フロントエンド
pnpm dev:ai       # AIサーバー（Ollama）
```

### PM2での運用

```bash
# PM2インストール
pnpm add -g pm2

# サービス起動
pnpm start  # pm2 start ecosystem.config.js

# 状態確認
pm2 status
pm2 logs

# 停止
pnpm stop
```

### systemdでの本番運用

```bash
# サービスファイルインストール
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload

# サービス有効化・起動
sudo systemctl enable shodo-backend shodo-frontend shodo-ai
sudo systemctl start shodo-backend shodo-frontend shodo-ai

# 状態確認
sudo systemctl status shodo-*
```

## 🔄 Ollama → vLLM移行

### Step 1: vLLMセットアップ

```bash
# Python仮想環境作成
python -m venv venv
source venv/bin/activate

# vLLMインストール（CUDA必須）
pip install vllm

# モデルダウンロード（AWQ量子化版、5GB）
huggingface-cli download TheBloke/Llama-2-7B-Chat-AWQ
```

### Step 2: 環境変数切り替え

```bash
# .envを編集
INFERENCE_ENGINE=vllm
VLLM_URL=http://localhost:8000
MODEL_NAME=TheBloke/Llama-2-7B-Chat-AWQ
```

### Step 3: vLLMサーバー起動

```bash
# 開発環境
INFERENCE_ENGINE=vllm pnpm dev

# 本番環境（systemd）
sudo systemctl stop shodo-ai
sudo systemctl edit shodo-ai  # ExecStartをvLLM用に変更
sudo systemctl start shodo-ai
```

## 📊 パフォーマンス比較

| 構成 | 起動時間 | メモリ使用 | レスポンス | GPU必須 |
|-----|---------|-----------|-----------|---------|
| Ollama (7B) | 30秒 | 8GB | 1-2秒 | ❌ |
| vLLM (7B AWQ) | 1分 | 6GB | 0.2秒 | ✅ |
| vLLM (70B) | 3分 | 40GB | 0.5秒 | ✅ |

## 🔧 設定ファイル

### .tool-versions (asdf)
```
nodejs 20.11.0
python 3.11.7
postgres 15.5
redis 7.2.4
```

### pnpm-workspace.yaml
```yaml
packages:
  - 'frontend'
  - 'backend'
  - 'ai-server'
```

### ecosystem.config.js (PM2)
```javascript
module.exports = {
  apps: [
    {
      name: 'shodo-backend',
      script: './backend/src/main.js',
      instances: 'max',
      exec_mode: 'cluster'
    },
    // ...
  ]
}
```

## 🐛 トラブルシューティング

### Ollamaが起動しない

```bash
# サービス再起動
ollama serve

# ポート確認
lsof -i :11434
```

### pnpm devでエラー

```bash
# node_modules再インストール
pnpm clean
pnpm install

# ポート競合確認
lsof -i :3000
lsof -i :8000
lsof -i :8001
```

### PostgreSQL接続エラー

```bash
# 状態確認
pg_ctl status -D ~/.asdf/installs/postgres/15.5/data

# 再起動
pg_ctl restart -D ~/.asdf/installs/postgres/15.5/data
```

## 📈 スケーリング戦略

```
開発初期:
  Ollama + 開発サーバー（pnpm dev）
  ↓
小規模本番:
  Ollama + PM2（クラスタモード）
  ↓
中規模本番:
  vLLM (7B) + PM2 + nginx
  ↓
大規模本番:
  vLLM (70B) + systemd + HAProxy + Redis Cluster
```

## 🎯 推奨構成

### 最小構成（開発）
- CPU: 4コア
- RAM: 8GB
- Storage: 20GB
- GPU: 不要

### 推奨構成（Ollama本番）
- CPU: 8コア
- RAM: 16GB
- Storage: 50GB
- GPU: 不要

### 高性能構成（vLLM本番）
- CPU: 16コア
- RAM: 32GB
- Storage: 100GB
- GPU: RTX 3090以上

## 🚦 ヘルスチェック

```bash
# 全サービス状態確認
curl http://localhost:8000/health  # Backend
curl http://localhost:8001/health  # AI Server
curl http://localhost:3000         # Frontend

# PM2モニタリング
pm2 monit

# systemdログ
journalctl -u shodo-backend -f
```

## 📝 まとめ

**最短パス**: 
```bash
./setup.sh && pnpm dev
```

**本番移行**:
```bash
pnpm build && pnpm start
```

**高性能化**:
```bash
INFERENCE_ENGINE=vllm pnpm start
```

これで**Docker不要**で、**5分で開発開始**、必要に応じて**段階的に本番環境へ移行**できます！