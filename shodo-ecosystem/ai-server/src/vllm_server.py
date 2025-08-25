from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import os
from fastapi import FastAPI
from prometheus_client import Counter

# Prometheus metrics
REQUEST_COUNTER = Counter(
	"http_requests_total",
	"Total HTTP requests",
	["method", "route", "status"]
)
PROM_AVAILABLE = os.getenv("PROMETHEUS_ENABLED") == "true"

app = FastAPI(title="vLLM Server for Shodo Ecosystem")

# CORS設定（明示ホワイトリスト）
AI_INTERNAL_TOKEN = os.getenv("AI_INTERNAL_TOKEN")
AI_CORS_ORIGINS = os.getenv("AI_CORS_ORIGINS")
_allowed_origins = [o.strip() for o in AI_CORS_ORIGINS.split(",")] if AI_CORS_ORIGINS else [
	"http://localhost:3000",
	"http://localhost"
]
app.add_middleware(
	CORSMiddleware,
	allow_origins=_allowed_origins,
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"]
)

@app.middleware("http")
async def metrics_middleware(request, call_next):
	response = await call_next(request)
	try:
		if PROM_AVAILABLE:
			route = request.url.path
			REQUEST_COUNTER.labels(method=request.method, route=route, status=response.status_code).inc()
	except Exception:
		pass
	return response

# 内部API保護: /v1/* は内部トークン（設定時）を要求。/health,/metrics,/v1/models は除外
@app.middleware("http")
async def internal_auth_middleware(request, call_next):
	try:
		path = request.url.path
		public_paths = {"/health", "/metrics", "/v1/models"}
		if path in public_paths:
			return await call_next(request)
		if path.startswith("/v1/") and AI_INTERNAL_TOKEN:
			h_token = request.headers.get("X-Internal-Token")
			auth = request.headers.get("Authorization") or ""
			bearer = auth.split(" ")[-1] if auth.startswith("Bearer ") else None
			provided = h_token or bearer
			if not provided or provided != AI_INTERNAL_TOKEN:
				from fastapi.responses import JSONResponse
				return JSONResponse(status_code=403, content={"detail": "Forbidden"})
		return await call_next(request)
	except Exception:
		return await call_next(request)

if __name__ == "__main__":
	uvicorn.run(app, host="0.0.0.0", port=8000)