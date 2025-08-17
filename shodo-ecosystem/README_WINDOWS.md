# 🚀 Shodo Ecosystem - Windows環境セットアップガイド

## 📋 前提条件

### 必須ソフトウェア

1. **Docker Desktop for Windows**
   - [ダウンロードページ](https://www.docker.com/products/docker-desktop)
   - インストール後、Docker Desktopを起動してください

2. **WSL2（推奨）**
   - パフォーマンス向上のため、WSL2バックエンドの使用を推奨
   - PowerShellを管理者権限で開き、以下を実行：
   ```powershell
   wsl --install
   ```

### システム要件

- **OS**: Windows 10 64-bit (Pro/Enterprise/Education) Build 19041以降、またはWindows 11
- **CPU**: 4コア以上
- **RAM**: 8GB以上（16GB推奨）
- **ストレージ**: 50GB以上の空き容量
- **仮想化**: BIOS/UEFIで仮想化を有効化

## 🛠️ セットアップ手順

### 1. Docker Desktopの設定

1. Docker Desktopを起動
2. 設定（Settings）を開く
3. **General**タブで以下を確認：
   - ✅ Use WSL 2 based engine（推奨）
4. **Resources** → **WSL Integration**：
   - ✅ Enable integration with my default WSL distro

### 2. プロジェクトのダウンロード

```cmd
git clone https://github.com/your-org/shodo-ecosystem.git
cd shodo-ecosystem
```

GitがインストールされていなければZIPファイルをダウンロードして解凍してください。

### 3. 初期セットアップ

```cmd
setup.bat
```

このコマンドで以下が実行されます：
- 必要なディレクトリの作成
- 環境変数ファイルの設定
- Docker環境の確認

### 4. Dockerイメージのビルド

```cmd
build.bat
```

初回は10-20分程度かかる場合があります。

### 5. サービスの起動

```cmd
start.bat
```

自動的にブラウザが開き、http://localhost:3000 にアクセスします。

## 📖 使い方

### サービスへのアクセス

- **フロントエンド**: http://localhost:3000
- **バックエンドAPI**: http://localhost:8000
- **APIドキュメント**: http://localhost:8000/docs

### 基本操作

| コマンド | 説明 |
|---------|------|
| `start.bat` | サービスを起動 |
| `stop.bat` | サービスを停止 |
| `logs.bat` | ログを表示（Ctrl+Cで終了） |
| `clean.bat` | 全データを削除してクリーンアップ |

## ⚠️ Windows特有の注意事項

### 1. ファイアウォール

初回起動時にWindowsファイアウォールの警告が表示される場合があります。
「アクセスを許可する」を選択してください。

### 2. ポート競合

以下のポートが使用されます。他のアプリケーションと競合しないか確認してください：
- 3000 (Frontend)
- 8000 (Backend API)
- 8001 (vLLM Server)
- 5432 (PostgreSQL)
- 6379 (Redis)

### 3. パフォーマンス

- WSL2バックエンドの使用を強く推奨します
- Docker Desktop設定でメモリを8GB以上割り当てることを推奨
- Windows Defenderのリアルタイムスキャンから除外設定を推奨

### 4. GPU使用について

Windows環境では、現在CPUモードで動作します。GPU使用には以下が必要です：
- NVIDIA GPU (CUDA対応)
- NVIDIA Docker Runtime
- WSL2でのCUDAサポート設定

## 🔧 トラブルシューティング

### Docker Desktopが起動しない

1. Hyper-Vが有効か確認：
   ```powershell
   Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -All
   ```

2. 仮想化が有効か確認：
   - タスクマネージャー → パフォーマンス → CPU
   - 「仮想化」が「有効」になっているか確認

### ビルドエラー

```cmd
REM Dockerのキャッシュをクリア
docker system prune -a

REM 再ビルド
build.bat
```

### ポート使用中エラー

```cmd
REM 使用中のポートを確認
netstat -ano | findstr :3000
netstat -ano | findstr :8000

REM プロセスを終了（PIDを指定）
taskkill /PID [プロセスID] /F
```

### WSL2関連のエラー

```powershell
# WSL2を更新
wsl --update

# WSLをリセット
wsl --shutdown
```

## 📊 リソース使用量

### 推奨設定（Docker Desktop）

Settings → Resources で以下を設定：

- **CPUs**: 4以上
- **Memory**: 8GB以上
- **Swap**: 2GB
- **Disk image size**: 64GB

## 🆘 サポート

問題が解決しない場合：

1. `logs.bat`でログを確認
2. Docker Desktopを再起動
3. PCを再起動
4. [GitHub Issues](https://github.com/your-org/shodo-ecosystem/issues)で報告

## 📝 開発メモ

### Windows環境での制限事項

1. **ファイル監視**: Reactのホットリロードが遅い場合があります
2. **パス長制限**: 260文字を超えるパスでエラーが発生する可能性
3. **改行コード**: GitでCRLF/LF変換に注意

### 推奨開発環境

- **エディタ**: Visual Studio Code
- **ターミナル**: Windows Terminal
- **Git設定**:
  ```cmd
  git config --global core.autocrlf true
  ```

---

**Windows環境でも快適にShodo Ecosystemをお使いいただけます！**