from cachetools import TTLCache
from ...utils.correlation import get_correlation_id
from pydantic import BaseModel, ValidationError, Field
from typing import Dict, Any, Optional, List
import logging
import requests

logger = logging.getLogger(__name__)

class DualPathEngine:
    def __init__(self, engine: str, api_key: str, model_name: str):
        self.engine = engine
        self.api_key = api_key
        self.model_name = model_name
        self.ambiguity_dict = self._initialize_ambiguity_dict()
        
        # AIレスポンスのスキーマ定義（堅牢化）
        class _AISchema(BaseModel):
            intent: str = Field(default="unknown")
            confidence: float = Field(ge=0.0, le=1.0, default=0.0)
            entities: Dict[str, Any] = Field(default_factory=dict)
            service: Optional[str] = None
            suggestions: List[str] = Field(default_factory=list)

        self._AISchema = _AISchema

    def _initialize_ambiguity_dict(self):
        # Placeholder for actual ambiguity dictionary initialization
        return {}

    def _ai_based_analysis(self, text_in: str) -> Dict[str, Any] | None:
        """
        AIベースの分析を実行し、結果を正規化して返します。
        """
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            if self.engine == 'vllm':
                url = f"https://api.vllm.ai/v1/models/{self.model_name}/generate"
                payload = {
                    "prompt": text_in,
                    "max_tokens": 100,
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "stream": False
                }
            else:
                url = f"https://api.openai.com/v1/chat/completions"
                payload = {
                    "model": self.model_name,
                    "messages": [{"role": "user", "content": text_in}],
                    "max_tokens": 100,
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "stream": False
                }

            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()

            if response.status_code == 200:
                data = response.json()
                try:
                    if self.engine == 'vllm':
                        # vLLM側は直接スキーマに適合することを期待し、バリデーション
                        normalized = self._AISchema.model_validate(data)
                        return normalized.model_dump()
                    else:
                        # 代理応答を正規化してからバリデーション
                        text_out = data.get('choices', [{}])[0].get('message', {}).get('content', '')
                        candidate = {"intent": "unknown", "confidence": 0.6, "entities": {"raw": text_out}}
                        normalized = self._AISchema.model_validate(candidate)
                        return normalized.model_dump()
                except ValidationError:
                    logger.error("AI response schema validation failed")
                    return None
            else:
                logger.error(f"AI analysis failed: {response.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Error during AI analysis: {e}")
            return None

    def analyze(self, text_in: str) -> Dict[str, Any] | None:
        """
        テキストを分析し、結果を返します。
        """
        correlation_id = get_correlation_id()
        logger.info(f"Analyzing text with correlation ID: {correlation_id}")

        # 1. 曖昧性チェック
        if text_in in self.ambiguity_dict:
            logger.warning(f"Ambiguity detected for text: {text_in}")
            return self.ambiguity_dict[text_in]

        # 2. AIベースの分析
        ai_result = self._ai_based_analysis(text_in)
        if ai_result:
            logger.info(f"AI analysis successful for text: {text_in}")
            return ai_result
        else:
            logger.warning(f"AI analysis failed for text: {text_in}")
            return None