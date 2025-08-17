"""
vLLM推論サーバー
GPT-OSS-20Bモデルを使用した高速推論エンジン
"""

import os
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import asyncio
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# vLLMのインポート（実際の環境では有効化）
try:
    from vllm import LLM, SamplingParams
    from vllm.engine.arg_utils import AsyncEngineArgs
    from vllm.engine.async_llm_engine import AsyncLLMEngine
    VLLM_AVAILABLE = True
except ImportError:
    VLLM_AVAILABLE = False
    logging.warning("vLLM not available. Running in mock mode.")

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 環境変数から設定を読み込み
MODEL_NAME = os.getenv("MODEL_NAME", "openai/gpt-oss-20b")
QUANTIZATION = os.getenv("QUANTIZATION", "awq")
GPU_MEMORY_UTILIZATION = float(os.getenv("GPU_MEMORY_UTILIZATION", "0.95"))
MAX_MODEL_LEN = int(os.getenv("MAX_MODEL_LEN", "128000"))

app = FastAPI(title="vLLM Server for Shodo Ecosystem")

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# リクエスト/レスポンスモデル
class CompletionRequest(BaseModel):
    prompt: str
    max_tokens: int = 2048
    temperature: float = 0.3
    top_p: float = 0.95
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    stop: Optional[List[str]] = None
    stream: bool = False

class CompletionResponse(BaseModel):
    id: str
    object: str = "text_completion"
    created: int
    model: str
    choices: List[Dict[str, Any]]
    usage: Dict[str, int]

class AnalysisRequest(BaseModel):
    text: str
    context: Optional[Dict[str, Any]] = None
    mode: str = "dual_path"  # "dual_path", "rule_only", "ai_only"

class AnalysisResponse(BaseModel):
    intent: str
    confidence: float
    entities: Dict[str, Any]
    service: Optional[str] = None
    requires_confirmation: bool = False
    suggestions: List[str] = []
    processing_path: str

# モックエンジン（開発用）
class MockLLMEngine:
    """開発環境用のモックエンジン"""
    
    async def generate(self, prompt: str, params: Dict) -> str:
        """モック生成"""
        await asyncio.sleep(0.1)  # 遅延をシミュレート
        
        # プロンプトに基づいた簡単な応答
        if "intent" in prompt.lower():
            return json.dumps({
                "intent": "export",
                "confidence": 0.85,
                "entities": {"target": "orders", "format": "csv"},
                "service": "shopify"
            })
        elif "曖昧" in prompt or "clarify" in prompt.lower():
            return json.dumps({
                "suggestions": [
                    "どのサービスの操作をお望みですか？",
                    "具体的な数値を教えてください",
                    "対象期間を指定してください"
                ]
            })
        else:
            return "モック応答: " + prompt[:100]

# エンジンのグローバルインスタンス
llm_engine = None

@app.on_event("startup")
async def startup_event():
    """サーバー起動時の初期化"""
    global llm_engine
    
    if VLLM_AVAILABLE:
        try:
            # vLLMエンジンの初期化
            engine_args = AsyncEngineArgs(
                model=MODEL_NAME,
                quantization=QUANTIZATION,
                gpu_memory_utilization=GPU_MEMORY_UTILIZATION,
                max_model_len=MAX_MODEL_LEN,
                trust_remote_code=True,
            )
            llm_engine = AsyncLLMEngine.from_engine_args(engine_args)
            logger.info(f"vLLM engine initialized with model: {MODEL_NAME}")
        except Exception as e:
            logger.error(f"Failed to initialize vLLM: {e}")
            llm_engine = MockLLMEngine()
    else:
        logger.info("Using mock LLM engine for development")
        llm_engine = MockLLMEngine()

@app.get("/health")
async def health_check():
    """ヘルスチェックエンドポイント"""
    return {
        "status": "healthy",
        "model": MODEL_NAME,
        "vllm_available": VLLM_AVAILABLE,
        "quantization": QUANTIZATION
    }

@app.get("/v1/models")
async def list_models():
    """利用可能なモデルのリスト"""
    return {
        "object": "list",
        "data": [
            {
                "id": MODEL_NAME,
                "object": "model",
                "created": 1700000000,
                "owned_by": "shodo-ecosystem",
                "permission": [],
                "root": MODEL_NAME,
                "parent": None,
            }
        ]
    }

@app.post("/v1/completions")
async def create_completion(request: CompletionRequest):
    """テキスト補完エンドポイント"""
    try:
        if VLLM_AVAILABLE and llm_engine and hasattr(llm_engine, 'generate'):
            # vLLMを使用した生成
            sampling_params = SamplingParams(
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                top_p=request.top_p,
                frequency_penalty=request.frequency_penalty,
                presence_penalty=request.presence_penalty,
                stop=request.stop,
            )
            
            results = await llm_engine.generate(
                request.prompt,
                sampling_params,
                request_id=None
            )
            
            text = results[0].outputs[0].text
        else:
            # モックエンジンを使用
            text = await llm_engine.generate(
                request.prompt,
                {
                    "max_tokens": request.max_tokens,
                    "temperature": request.temperature
                }
            )
        
        import time
        return CompletionResponse(
            id=f"cmpl-{int(time.time())}",
            created=int(time.time()),
            model=MODEL_NAME,
            choices=[
                {
                    "text": text,
                    "index": 0,
                    "logprobs": None,
                    "finish_reason": "stop"
                }
            ],
            usage={
                "prompt_tokens": len(request.prompt.split()),
                "completion_tokens": len(text.split()),
                "total_tokens": len(request.prompt.split()) + len(text.split())
            }
        )
    except Exception as e:
        logger.error(f"Completion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/analyze")
async def analyze_text(request: AnalysisRequest):
    """自然言語解析エンドポイント（二重経路解析）"""
    try:
        # ルールベース解析（高速パス）
        rule_result = await rule_based_analysis(request.text)
        
        # AI解析が必要かチェック
        if request.mode == "rule_only" or rule_result["confidence"] > 0.9:
            return AnalysisResponse(
                intent=rule_result["intent"],
                confidence=rule_result["confidence"],
                entities=rule_result["entities"],
                service=rule_result.get("service"),
                processing_path="rule"
            )
        
        # AI解析（詳細パス）
        if request.mode != "rule_only":
            ai_result = await ai_based_analysis(request.text, request.context)
            
            # 結果の統合
            merged_result = merge_analysis_results(rule_result, ai_result)
            
            return AnalysisResponse(
                intent=merged_result["intent"],
                confidence=merged_result["confidence"],
                entities=merged_result["entities"],
                service=merged_result.get("service"),
                requires_confirmation=merged_result["confidence"] < 0.7,
                suggestions=merged_result.get("suggestions", []),
                processing_path=merged_result["processing_path"]
            )
        
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def rule_based_analysis(text: str) -> Dict:
    """ルールベースの高速解析"""
    # パターンマッチング
    patterns = {
        r"(エクスポート|出力|ダウンロード)": {"intent": "export", "confidence": 0.9},
        r"(インポート|取り込み|アップロード)": {"intent": "import", "confidence": 0.9},
        r"(削除|消去|削除)": {"intent": "delete", "confidence": 0.85},
        r"(作成|新規|追加)": {"intent": "create", "confidence": 0.85},
        r"(更新|変更|修正)": {"intent": "update", "confidence": 0.85},
        r"(検索|探す|見つける)": {"intent": "search", "confidence": 0.8},
    }
    
    import re
    for pattern, result in patterns.items():
        if re.search(pattern, text):
            # エンティティ抽出
            entities = extract_entities(text)
            return {
                "intent": result["intent"],
                "confidence": result["confidence"],
                "entities": entities,
                "service": detect_service(text)
            }
    
    return {
        "intent": "unknown",
        "confidence": 0.3,
        "entities": {},
        "service": None
    }

async def ai_based_analysis(text: str, context: Optional[Dict]) -> Dict:
    """AI（GPT-OSS）を使用した詳細解析"""
    prompt = f"""
    以下のユーザー入力を解析し、JSONフォーマットで結果を返してください。

    ユーザー入力: {text}
    コンテキスト: {json.dumps(context or {}, ensure_ascii=False)}

    必要な情報:
    - intent: 操作の意図（export, import, create, update, delete, search, other）
    - confidence: 確信度（0.0-1.0）
    - entities: 抽出されたエンティティ（key-value形式）
    - service: 対象サービス（shopify, gmail, stripe等）
    - suggestions: 曖昧な場合の明確化のための質問（配列）

    JSON形式で応答:
    """
    
    response = await llm_engine.generate(prompt, {"max_tokens": 512, "temperature": 0.3})
    
    try:
        if isinstance(response, str):
            # JSON文字列をパース
            if response.startswith("```json"):
                response = response[7:-3]
            elif response.startswith("```"):
                response = response[3:-3]
            result = json.loads(response)
        else:
            result = response
    except:
        result = {
            "intent": "unknown",
            "confidence": 0.5,
            "entities": {},
            "suggestions": ["もう少し詳しく教えてください"]
        }
    
    return result

def merge_analysis_results(rule_result: Dict, ai_result: Dict) -> Dict:
    """ルールベースとAIの結果を統合"""
    # 重み付け統合
    rule_weight = 0.4
    ai_weight = 0.6
    
    # 確信度の加重平均
    merged_confidence = (
        rule_result["confidence"] * rule_weight +
        ai_result.get("confidence", 0.5) * ai_weight
    )
    
    # intentの決定（確信度が高い方を採用）
    if rule_result["confidence"] > ai_result.get("confidence", 0):
        intent = rule_result["intent"]
        processing_path = "rule_primary"
    else:
        intent = ai_result.get("intent", "unknown")
        processing_path = "ai_primary"
    
    # エンティティのマージ
    merged_entities = {**rule_result["entities"], **ai_result.get("entities", {})}
    
    return {
        "intent": intent,
        "confidence": merged_confidence,
        "entities": merged_entities,
        "service": rule_result.get("service") or ai_result.get("service"),
        "suggestions": ai_result.get("suggestions", []),
        "processing_path": processing_path
    }

def extract_entities(text: str) -> Dict:
    """エンティティ抽出"""
    entities = {}
    
    # 日付パターン
    import re
    date_pattern = r"(\d{4}[年/-]\d{1,2}[月/-]\d{1,2}日?)"
    dates = re.findall(date_pattern, text)
    if dates:
        entities["date"] = dates[0]
    
    # 数値パターン
    number_pattern = r"(\d+(?:,\d{3})*(?:\.\d+)?)[円個件]?"
    numbers = re.findall(number_pattern, text)
    if numbers:
        entities["amount"] = numbers[0].replace(",", "")
    
    # サービス名
    services = ["Shopify", "Gmail", "Stripe", "Slack"]
    for service in services:
        if service.lower() in text.lower():
            entities["service"] = service.lower()
            break
    
    return entities

def detect_service(text: str) -> Optional[str]:
    """テキストからサービスを検出"""
    service_keywords = {
        "shopify": ["shopify", "ショッピファイ", "商品", "注文", "在庫"],
        "gmail": ["gmail", "メール", "送信", "受信"],
        "stripe": ["stripe", "ストライプ", "決済", "支払い", "課金"],
        "slack": ["slack", "スラック", "チャンネル", "メッセージ"]
    }
    
    text_lower = text.lower()
    for service, keywords in service_keywords.items():
        for keyword in keywords:
            if keyword in text_lower:
                return service
    
    return None

if __name__ == "__main__":
    uvicorn.run(
        "vllm_server:app",
        host="0.0.0.0",
        port=8001,
        reload=False,
        log_level="info"
    )