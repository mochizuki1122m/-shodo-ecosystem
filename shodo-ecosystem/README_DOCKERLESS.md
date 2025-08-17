# Shodo Ecosystem - Docker不要版セットアップガイド

## 🚀 クイックスタート（Windows/Mac/Linux）

### 最短経路（3分で起動）

```bash
# 1. Ollamaインストール（各OS用）
# Windows: https://ollama.com/download/windows
# Mac: brew install ollama
# Linux: curl -fsSL https://ollama.ai/install.sh | sh

# 2. モデル取得
ollama pull mistral

# 3. 依存インストール
npm install
cd frontend && npm install --legacy-peer-deps && cd ..

# 4. 起動
npm run dev  # または start-simple.bat (Windows)
```

ブラウザで `http://localhost:3000/simple.html` を開く

---

## 📋 前提条件

### 必須
- **Node.js 20 LTS** ([ダウンロード](https://nodejs.org/))
- **Python 3.10+** ([ダウンロード](https://www.python.org/))
- **Git** ([ダウンロード](https://git-scm.com/))

### 推奨
- **pnpm** - 高速なパッケージマネージャ
  ```bash
  npm install -g pnpm
  ```
- **PM2** - プロセス管理
  ```bash
  npm install -g pm2
  ```

### オプション（用途別）
- **Ollama** - ローカルLLM（推奨）
- **CUDA** - GPU利用時のみ
- **asdf** - バージョン管理

---

## 🛠️ セットアップ手順

### 1. 環境変数の設定

```bash
cp .env.example .env
# .envファイルを編集
```

主要な設定項目：
```env
# LLM設定（Ollama使用時）
LLM_PROVIDER=ollama
OPENAI_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=mistral

# ポート設定
API_PORT=8000
FRONTEND_PORT=8080
```

### 2. Ollama セットアップ（推奨）

#### Windows
```batch
setup-ollama.bat
```

#### Mac/Linux
```bash
# インストール
curl -fsSL https://ollama.ai/install.sh | sh

# 起動
ollama serve

# モデル取得
ollama pull mistral
```

### 3. 依存関係のインストール

```bash
# pnpm使用（推奨）
pnpm install

# または npm
npm install
cd frontend && npm install --legacy-peer-deps && cd ..
```

### 4. サービス起動

#### 開発環境（シンプル）

**Windows:**
```batch
start-simple.bat
```

**Mac/Linux:**
```bash
# Backend
cd backend && python3 simple_server.py &

# Frontend
cd frontend/public && python3 -m http.server 3000 &
```

#### 本番環境（PM2使用）

**Windows:**
```batch
start-production.bat
```

**Mac/Linux:**
```bash
pm2 start ecosystem.config.js
pm2 save
pm2 startup  # 自動起動設定
```

---

## 🔧 詳細設定

### LLMプロバイダの選択

#### Option 1: Ollama（推奨）
- **メリット**: 簡単、CPU対応、プライバシー保護
- **デメリット**: 速度が遅い場合がある

```env
LLM_PROVIDER=ollama
OPENAI_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=mistral  # または qwen2.5:7b, llama3 など
```

#### Option 2: vLLM（GPU環境）
- **メリット**: 高速、大規模モデル対応
- **デメリット**: GPU必須、セットアップ複雑

```bash
# インストール
pip install vllm torch

# 起動
python -m vllm.entrypoints.openai.api_server \
  --model mistralai/Mistral-7B-Instruct-v0.2 \
  --port 8001
```

```env
LLM_PROVIDER=vllm
OPENAI_BASE_URL=http://localhost:8001/v1
```

#### Option 3: OpenAI API
- **メリット**: 最高品質、メンテナンス不要
- **デメリット**: コスト、インターネット必須

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

### プロセス管理

#### PM2（推奨）

```bash
# 起動
pm2 start ecosystem.config.js

# 監視
pm2 monit

# ログ確認
pm2 logs

# 再起動
pm2 restart all

# 停止
pm2 stop all
```

#### systemd（Linux本番環境）

```bash
# サービスファイル作成
sudo cp systemd/*.service /etc/systemd/system/

# 有効化
sudo systemctl enable --now shodo-backend
sudo systemctl enable --now shodo-frontend
```

### バージョン固定（チーム開発）

```bash
# asdfでバージョン固定
echo "nodejs 20.12.2" >> .tool-versions
echo "python 3.11.9" >> .tool-versions
asdf install

# lockファイル厳守
pnpm install --frozen-lockfile
```

---

## 📊 パフォーマンスチューニング

### メモリ設定

```javascript
// ecosystem.config.js
{
  name: 'shodo-frontend',
  max_memory_restart: '500M',  // メモリ制限
  // ...
}
```

### Ollama最適化

```bash
# CPUスレッド数を指定
OLLAMA_NUM_THREADS=8 ollama serve

# 小型モデルを使用（高速化）
ollama pull phi3:mini
```

### ポート変更

```env
# .env
API_PORT=3001
FRONTEND_PORT=8081
```

---

## 🔍 トラブルシューティング

### ポート競合

```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Mac/Linux
lsof -i :8000
kill -9 <PID>
```

### Ollama接続エラー

```bash
# サービス再起動
ollama serve

# API確認
curl http://localhost:11434/api/tags
```

### 依存関係エラー

```bash
# キャッシュクリア
npm cache clean --force
rm -rf node_modules package-lock.json
npm install
```

### Python環境エラー

```bash
# 仮想環境作成
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

---

## 🧹 クリーンアップ

```bash
# PM2プロセス削除
pm2 delete all
pm2 save

# ログ削除
rm -rf logs/*

# 依存関係削除
rm -rf node_modules
rm -rf frontend/node_modules
rm -rf venv

# Ollamaモデル削除
ollama rm mistral
```

---

## 📈 本番環境への移行

1. **環境変数の本番設定**
   ```env
   NODE_ENV=production
   LOG_LEVEL=warn
   ```

2. **SSL/TLS設定**（nginx推奨）

3. **監視設定**
   - PM2 Plus
   - Datadog
   - New Relic

4. **バックアップ設定**
   - データベース定期バックアップ
   - ログローテーション

5. **セキュリティ強化**
   - ファイアウォール設定
   - rate limiting
   - CORS設定

---

## 📚 参考リンク

- [Ollama Documentation](https://github.com/ollama/ollama)
- [PM2 Documentation](https://pm2.keymetrics.io/)
- [vLLM Documentation](https://docs.vllm.ai/)
- [Node.js Best Practices](https://github.com/goldbergyoni/nodebestpractices)

---

**サポート**: 問題が発生した場合は、Issueを作成してください。