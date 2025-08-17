# 📘 Shodo Ecosystem - Windows フル機能版セットアップガイド

## 🎯 このガイドについて

Windows環境でShodo Ecosystemのフル機能版を起動するための完全ガイドです。
AIによる自然言語処理、プレビュー機能、セキュア認証など、すべての機能を利用できます。

---

## 📋 前提条件

### 必須要件

| 項目 | 要件 | 確認方法 |
|------|------|----------|
| **OS** | Windows 10 (Build 19041以降) または Windows 11 | `winver` コマンドで確認 |
| **CPU** | 4コア以上（8コア推奨） | タスクマネージャー → パフォーマンス |
| **メモリ** | 8GB以上（16GB推奨） | タスクマネージャー → パフォーマンス |
| **ストレージ** | 50GB以上の空き容量 | エクスプローラーでCドライブ確認 |
| **仮想化** | 有効化されていること | タスクマネージャー → パフォーマンス → CPU → 仮想化 |

### 必須ソフトウェア

1. **Docker Desktop for Windows**
   - [公式サイト](https://www.docker.com/products/docker-desktop)からダウンロード
   - WSL2バックエンドを推奨

2. **Git for Windows**（推奨）
   - [公式サイト](https://git-scm.com/download/win)からダウンロード

---

## 🚀 クイックスタート（最速15分）

### ステップ1: Docker Desktopのインストール

1. [Docker Desktop](https://www.docker.com/products/docker-desktop)をダウンロード
2. インストーラーを実行（管理者権限）
3. インストール完了後、PCを再起動
4. Docker Desktopを起動し、初期設定を完了

### ステップ2: プロジェクトの取得

**Gitを使用する場合:**
```cmd
git clone https://github.com/your-org/shodo-ecosystem.git
cd shodo-ecosystem
```

**Gitがない場合:**
1. [リポジトリ](https://github.com/your-org/shodo-ecosystem)からZIPをダウンロード
2. 任意のフォルダに解凍（例: `C:\Projects\shodo-ecosystem`）
3. コマンドプロンプトでそのフォルダに移動

### ステップ3: フル機能版セットアップ

**管理者権限でコマンドプロンプトを開き:**
```cmd
cd C:\Projects\shodo-ecosystem
setup-windows-full.bat
```

このスクリプトが自動的に以下を実行:
- Docker環境の確認
- 必要なディレクトリの作成
- 環境変数の設定
- Dockerイメージのビルド
- サービスの起動

### ステップ4: アクセス

セットアップ完了後、以下のURLにアクセス:
- **メインUI**: http://localhost:3000
- **API ドキュメント**: http://localhost:8000/docs

---

## 🔧 詳細セットアップ

### 1. WSL2の有効化（推奨）

PowerShellを管理者権限で開き:

```powershell
# WSL2を有効化
wsl --install

# WSL2を既定のバージョンに設定
wsl --set-default-version 2

# Ubuntu（または好みのディストリビューション）をインストール
wsl --install -d Ubuntu
```

### 2. Docker Desktop設定

1. Docker Desktopを起動
2. Settings（設定）を開く
3. **General**タブ:
   - ✅ Use WSL 2 based engine
   - ✅ Start Docker Desktop when you log in

4. **Resources** → **WSL Integration**:
   - ✅ Enable integration with my default WSL distro
   - 使用するディストリビューションを選択

5. **Resources** → **Advanced**:
   - CPUs: 4以上
   - Memory: 8GB以上
   - Swap: 2GB
   - Disk image size: 64GB

### 3. Ollama設定（ローカルLLM使用）

```cmd
# Ollamaのセットアップ
setup-ollama-windows.bat
```

推奨モデル:
- **mistral** (7B) - バランス型
- **qwen2.5** (7B) - 日本語対応良好
- **phi3** (3.8B) - 軽量・高速

### 4. 環境変数のカスタマイズ

`.env.windows`を`.env`にコピーして編集:

```cmd
copy .env.windows .env
notepad .env
```

主要な設定項目:

```env
# LLMプロバイダー選択
LLM_PROVIDER=ollama  # または openai, mock

# Ollama使用時
OPENAI_BASE_URL=http://host.docker.internal:11434/v1
OLLAMA_MODEL=mistral

# OpenAI API使用時
# OPENAI_API_KEY=sk-your-api-key-here
```

---

## 📦 起動と停止

### サービスの起動

```cmd
# フル機能版を起動
start-windows.bat
```

### サービスの停止

```cmd
# すべてのサービスを停止
stop-windows.bat
```

### ログの確認

```cmd
# すべてのサービスのログを表示
docker-compose -f docker-compose.windows.yml logs -f

# 特定のサービスのログ
docker-compose -f docker-compose.windows.yml logs -f backend
docker-compose -f docker-compose.windows.yml logs -f frontend
```

---

## 🎮 使い方

### 基本操作フロー

1. **ブラウザでアクセス**
   - http://localhost:3000 を開く

2. **ログイン**
   - 開発環境: 「デモアカウントでログイン」をクリック
   - 本番環境: 設定したアカウントでログイン

3. **自然言語で操作**
   - 例: 「Shopifyの今月の売上を確認」
   - 例: 「商品価格を10%値下げ」
   - 例: 「在庫が少ない商品をリストアップ」

4. **プレビューで確認**
   - 変更内容をプレビューで確認
   - 問題なければ「適用」をクリック

### サンプル操作

```
入力例:
- 「Shopifyの商品一覧を表示して」
- 「売上が多い順に並べ替えて」
- 「価格を1000円以上の商品だけ表示」
- 「選択した商品を10%値引き」
```

---

## 🔍 トラブルシューティング

### Docker Desktopが起動しない

```powershell
# Hyper-Vを有効化
Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -All

# 仮想化が有効か確認
# タスクマネージャー → パフォーマンス → CPU → 仮想化: 有効
```

### ポート使用中エラー

```cmd
# 使用中のポートを確認
netstat -ano | findstr :3000
netstat -ano | findstr :8000

# プロセスを終了（PIDを指定）
taskkill /PID [プロセスID] /F
```

### ビルドエラー

```cmd
# Dockerキャッシュをクリア
docker system prune -a

# 再ビルド
docker-compose -f docker-compose.windows.yml build --no-cache
```

### WSL2関連のエラー

```powershell
# WSL2を更新
wsl --update

# WSLをリセット
wsl --shutdown

# Dockerサービスを再起動
Restart-Service docker
```

### メモリ不足

`.wslconfig`ファイルを作成（`C:\Users\[ユーザー名]\.wslconfig`）:

```ini
[wsl2]
memory=8GB
processors=4
swap=2GB
```

---

## 🚀 パフォーマンス最適化

### 1. Windows Defender除外設定

```powershell
# Docker関連フォルダを除外
Add-MpPreference -ExclusionPath "C:\ProgramData\Docker"
Add-MpPreference -ExclusionPath "C:\Projects\shodo-ecosystem"
```

### 2. Docker Desktop設定

Settings → Resources → Advanced:
- **CPUs**: 物理コアの50-75%
- **Memory**: 物理メモリの50-75%
- **Swap**: 2-4GB

### 3. ファイル監視の最適化

`.env`ファイル:
```env
CHOKIDAR_USEPOLLING=true
CHOKIDAR_INTERVAL=3000
```

---

## 📊 システム要件別推奨設定

### 最小構成（8GB RAM）

```env
# .env設定
LLM_PROVIDER=mock  # または軽量モデル
MAX_OLD_SPACE_SIZE=2048
```

### 推奨構成（16GB RAM）

```env
# .env設定
LLM_PROVIDER=ollama
OLLAMA_MODEL=mistral
MAX_OLD_SPACE_SIZE=4096
```

### ハイエンド構成（32GB+ RAM、GPU搭載）

```env
# .env設定
LLM_PROVIDER=vllm
CUDA_VISIBLE_DEVICES=0
GPU_MEMORY_FRACTION=0.9
```

---

## 🔐 セキュリティ設定

### 本番環境への移行時

1. **環境変数の更新**
```env
NODE_ENV=production
JWT_SECRET_KEY=[強力なランダム文字列]
SESSION_SECRET=[強力なランダム文字列]
```

2. **HTTPS設定**
   - リバースプロキシ（nginx）の設定
   - SSL証明書の取得（Let's Encrypt推奨）

3. **ファイアウォール設定**
   - 必要なポートのみ開放
   - IPアドレス制限の設定

---

## 📚 参考リンク

- [Docker Desktop Documentation](https://docs.docker.com/desktop/windows/)
- [WSL2 Documentation](https://docs.microsoft.com/windows/wsl/)
- [Ollama Documentation](https://ollama.com/docs)
- [プロジェクトWiki](https://github.com/your-org/shodo-ecosystem/wiki)

---

## 🆘 サポート

問題が解決しない場合:

1. `logs`フォルダ内のログファイルを確認
2. `docker-compose -f docker-compose.windows.yml logs`でエラーを確認
3. [GitHub Issues](https://github.com/your-org/shodo-ecosystem/issues)で報告

---

## ✅ チェックリスト

起動前の確認:
- [ ] Docker Desktopがインストールされている
- [ ] Docker Desktopが起動している
- [ ] WSL2が有効化されている（推奨）
- [ ] 必要なポートが空いている（3000, 8000, 8001）
- [ ] 十分なディスク容量がある（50GB以上）
- [ ] 十分なメモリがある（8GB以上）

---

**Happy Coding with Shodo Ecosystem! 🚀**