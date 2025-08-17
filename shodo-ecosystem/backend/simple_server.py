"""
シンプルなFastAPIサーバー（動作確認用）
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# FastAPIアプリケーションの作成
app = FastAPI(
    title="Shodo Ecosystem API",
    description="AI-powered SaaS integration platform",
    version="1.0.0"
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ルートエンドポイント
@app.get("/")
async def root():
    return {
        "name": "Shodo Ecosystem API",
        "version": "1.0.0",
        "status": "running"
    }

# ヘルスチェック
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "database": "connected",
        "cache": "connected",
        "ai_server": "connected"
    }

# APIエンドポイントの例
@app.get("/api/v1/test")
async def test_endpoint():
    return {
        "message": "API is working!",
        "endpoint": "/api/v1/test"
    }

if __name__ == "__main__":
    print("Starting server at http://localhost:8000")
    print("API documentation at http://localhost:8000/docs")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )