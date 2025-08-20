"""
二重経路解析エンジン
ルールベースとAI解析を組み合わせた高精度NLP処理
"""

import asyncio
import hashlib
import json
import re
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

import httpx
from pydantic import BaseModel
from cachetools import TTLCache

logger = logging.getLogger(__name__)

@dataclass
class AnalysisResult:
    """解析結果データクラス"""
    intent: str                    # 操作意図
    confidence: float              # 確信度 (0.0-1.0)
    entities: Dict[str, Any]       # 抽出エンティティ
    service: Optional[str]         # 対象サービス
    requires_confirmation: bool    # 確認要否
    suggestions: List[str]         # 改善提案
    processing_path: str           # 'rule' | 'ai' | 'merged'
    processing_time_ms: float      # 処理時間

class DualPathEngine:
    """二重経路解析エンジン - タイムアウト/フォールバック対応"""
    
    def __init__(
        self, 
        vllm_url: str = None,
        cache_ttl: int = 300,
        timeout: int = 30,
        retry_count: int = 3,
        fallback_to_rules: bool = True
    ):
        """Initialize with dependency injection
        
        Args:
            vllm_url: AI server URL (ベースURL、/v1なし)
            cache_ttl: Cache TTL in seconds
            timeout: Request timeout in seconds
            retry_count: Number of retries
            fallback_to_rules: Fall back to rule-based when AI fails
        """
        # 設定から取得、またはデフォルト値使用
        from ...core.config import settings
        self.vllm_url = vllm_url or settings.vllm_url
        self.timeout = timeout or settings.vllm_timeout
        self.retry_count = retry_count or getattr(settings, 'vllm_retry_count', 3)
        self.cache_ttl = cache_ttl
        self.fallback_to_rules = fallback_to_rules
        
        # TTL付きキャッシュ（LRU + TTL）
        self.cache = TTLCache(maxsize=1000, ttl=cache_ttl)
        
        self.ai_available = True  # AI利用可能フラグ
        self.last_ai_check = datetime.now()
        
        # ルールベース設定
        self.patterns = self._initialize_patterns()
        self.ambiguity_dict = self._initialize_ambiguity_dict()
        
    def _initialize_patterns(self) -> Dict:
        """パターン定義の初期化"""
        return {
            # 基本操作パターン
            r"(エクスポート|出力|ダウンロード|書き出)": {
                "intent": "export",
                "confidence": 0.9
            },
            r"(インポート|取り込み|アップロード|読み込)": {
                "intent": "import",
                "confidence": 0.9
            },
            r"(削除|消去|取り消し|クリア)": {
                "intent": "delete",
                "confidence": 0.85
            },
            r"(作成|新規|追加|登録)": {
                "intent": "create",
                "confidence": 0.85
            },
            r"(更新|変更|修正|編集)": {
                "intent": "update",
                "confidence": 0.85
            },
            r"(検索|探す|見つける|抽出)": {
                "intent": "search",
                "confidence": 0.8
            },
            r"(表示|見る|確認|チェック)": {
                "intent": "view",
                "confidence": 0.8
            },
            r"(送信|送る|転送|共有)": {
                "intent": "send",
                "confidence": 0.85
            },
            
            # Shopify特化パターン
            r"(商品|プロダクト|アイテム).*(登録|追加)": {
                "intent": "create_product",
                "confidence": 0.95,
                "service": "shopify"
            },
            r"(注文|オーダー).*(確認|一覧|リスト)": {
                "intent": "view_orders",
                "confidence": 0.95,
                "service": "shopify"
            },
            r"(在庫|ストック).*(更新|変更)": {
                "intent": "update_inventory",
                "confidence": 0.9,
                "service": "shopify"
            },
            r"(顧客|カスタマー).*(検索|探)": {
                "intent": "search_customers",
                "confidence": 0.9,
                "service": "shopify"
            },
            
            # Gmail特化パターン
            r"(メール|mail).*(送信|送る)": {
                "intent": "send_email",
                "confidence": 0.95,
                "service": "gmail"
            },
            r"(未読|unread).*(確認|チェック)": {
                "intent": "check_unread",
                "confidence": 0.9,
                "service": "gmail"
            },
            
            # Stripe特化パターン
            r"(決済|支払い|ペイメント).*(確認|チェック)": {
                "intent": "check_payments",
                "confidence": 0.9,
                "service": "stripe"
            },
            r"(サブスク|定期|継続).*(課金|決済)": {
                "intent": "manage_subscription",
                "confidence": 0.9,
                "service": "stripe"
            }
        }
    
    def _initialize_ambiguity_dict(self) -> Dict:
        """曖昧表現辞書の初期化"""
        return {
            # 相対的な量
            'もっと': {'type': 'relative', 'default_ratio': 1.2, 'direction': 'increase'},
            'もう少し': {'type': 'relative', 'default_ratio': 1.1, 'direction': 'increase'},
            '少し': {'type': 'relative', 'default_ratio': 1.1, 'direction': 'increase'},
            'かなり': {'type': 'relative', 'default_ratio': 1.5, 'direction': 'increase'},
            '大幅に': {'type': 'relative', 'default_ratio': 2.0, 'direction': 'increase'},
            'ちょっと': {'type': 'relative', 'default_ratio': 0.9, 'direction': 'decrease'},
            
            # スタイル表現
            '目立つ': {'type': 'style', 'attributes': ['bold', 'large', 'colorful']},
            '控えめ': {'type': 'style', 'attributes': ['small', 'muted', 'simple']},
            'シンプル': {'type': 'style', 'attributes': ['minimal', 'clean', 'basic']},
            '派手': {'type': 'style', 'attributes': ['bright', 'bold', 'decorative']},
            
            # 時間表現
            '早く': {'type': 'time', 'urgency': 'high'},
            '急いで': {'type': 'time', 'urgency': 'urgent'},
            'ゆっくり': {'type': 'time', 'urgency': 'low'},
            '今すぐ': {'type': 'time', 'urgency': 'immediate'},
            
            # 価格表現
            '安く': {'type': 'price', 'direction': 'decrease', 'default_ratio': 0.8},
            '高く': {'type': 'price', 'direction': 'increase', 'default_ratio': 1.2},
            'お得に': {'type': 'price', 'direction': 'decrease', 'default_ratio': 0.7}
        }
    
    async def analyze_with_rules(self, text: str) -> Dict:
        """ルールベース解析のみ実行（API互換）"""
        normalized_text = self._normalize_input(text)
        result = await self._rule_based_analysis(normalized_text)
        return {
            "intent": result["intent"],
            "confidence": result["confidence"],
            "entities": result.get("entities", {}),
            "service": result.get("service"),
            "processing_path": "rule",
            "requires_confirmation": result["confidence"] < 0.7
        }
    
    async def analyze_with_ai(self, text: str, context: Optional[Dict] = None) -> Optional[Dict]:
        """AI解析のみ実行（API互換）"""
        normalized_text = self._normalize_input(text)
        result = await self._ai_based_analysis(normalized_text, context)
        return result
    
    def calculate_combined_score(self, rule_matches: Dict, ai_analysis: Optional[Dict]) -> float:
        """ルールベースとAI解析の統合スコアを計算（API互換）"""
        if not ai_analysis or "error" in ai_analysis:
            # ルールベースのみ
            if rule_matches.get("matches"):
                return rule_matches["matches"][0].get("confidence", 0.0)
            return 0.0
        
        # AI解析結果がある場合
        ai_confidence = ai_analysis.get("confidence", 0.0)
        
        # ルールベースの最大信頼度
        rule_confidence = 0.0
        if rule_matches.get("matches"):
            rule_confidence = rule_matches["matches"][0].get("confidence", 0.0)
        
        # 重み付き平均（AI解析を重視）
        return (rule_confidence * 0.3 + ai_confidence * 0.7)
    
    async def analyze(self, input_text: str, context: Optional[Dict] = None) -> AnalysisResult:
        """
        入力テキストを二重経路で解析
        
        Args:
            input_text: 解析対象の日本語テキスト
            context: 追加のコンテキスト情報
            
        Returns:
            AnalysisResult: 解析結果
        """
        start_time = datetime.now()
        
        # キャッシュチェック
        cache_key = self._generate_cache_key(input_text, context)
        if cache_key in self.cache:
            cached_result = self.cache[cache_key]
            cached_result.processing_time_ms = 0  # キャッシュヒット
            return cached_result
        
        # 前処理
        normalized = self._normalize_input(input_text)
        
        # 並列解析
        rule_task = asyncio.create_task(self._rule_based_analysis(normalized))
        ai_task = asyncio.create_task(self._ai_based_analysis(normalized, context))
        
        try:
            rule_result, ai_result = await asyncio.gather(rule_task, ai_task)
        except Exception as e:
            logger.error(f"Analysis error: {e}")
            # エラー時はルールベースのみ使用
            rule_result = await self._rule_based_analysis(normalized)
            ai_result = None
        
        # 結果統合
        if ai_result:
            merged_result = self._merge_results(rule_result, ai_result)
        else:
            merged_result = rule_result
            merged_result["processing_path"] = "rule_only"
        
        # 曖昧性解決
        if merged_result["confidence"] < 0.7:
            merged_result = await self._resolve_ambiguity(merged_result, input_text)
        
        # 処理時間計算
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        # 結果オブジェクト作成
        result = AnalysisResult(
            intent=merged_result.get("intent", "unknown"),
            confidence=merged_result.get("confidence", 0.0),
            entities=merged_result.get("entities", {}),
            service=merged_result.get("service"),
            requires_confirmation=merged_result.get("requires_confirmation", False),
            suggestions=merged_result.get("suggestions", []),
            processing_path=merged_result.get("processing_path", "unknown"),
            processing_time_ms=processing_time
        )
        
        # キャッシュ保存
        self.cache[cache_key] = result
        
        return result
    
    def _normalize_input(self, text: str) -> str:
        """入力テキストの正規化"""
        # 全角英数字を半角に変換
        text = text.translate(str.maketrans(
            '０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ',
            '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
        ))
        
        # 空白の正規化
        text = ' '.join(text.split())
        
        return text
    
    async def _rule_based_analysis(self, text: str) -> Dict:
        """ルールベース解析"""
        best_match = {
            "intent": "unknown",
            "confidence": 0.0,
            "entities": {},
            "service": None
        }
        
        # パターンマッチング
        for pattern, result in self.patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                if result["confidence"] > best_match["confidence"]:
                    best_match = {
                        "intent": result["intent"],
                        "confidence": result["confidence"],
                        "entities": self._extract_entities(text),
                        "service": result.get("service", self._detect_service(text))
                    }
        
        # 曖昧表現の検出
        ambiguous_terms = self._detect_ambiguous_terms(text)
        if ambiguous_terms:
            best_match["entities"]["ambiguous_terms"] = ambiguous_terms
            best_match["confidence"] *= 0.8  # 曖昧表現がある場合は確信度を下げる
        
        return best_match
    
    async def _ai_based_analysis(self, text: str, context: Optional[Dict]) -> Optional[Dict]:
        """AI（vLLM）を使用した解析"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.vllm_url}/v1/analyze",
                    json={
                        "text": text,
                        "context": context,
                        "mode": "ai_only"
                    },
                    timeout=5.0
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"AI analysis failed: {response.status_code}")
                    return None
                    
        except Exception as e:
            logger.error(f"AI analysis error: {e}")
            return None
    
    def _merge_results(self, rule_result: Dict, ai_result: Dict) -> Dict:
        """ルールベースとAIの結果を統合"""
        # 重み付け
        rule_weight = 0.4
        ai_weight = 0.6
        
        # 確信度の加重平均
        merged_confidence = (
            rule_result["confidence"] * rule_weight +
            ai_result.get("confidence", 0.5) * ai_weight
        )
        
        # より確信度の高い方のintentを採用
        if rule_result["confidence"] > ai_result.get("confidence", 0):
            intent = rule_result["intent"]
            processing_path = "rule_primary"
        else:
            intent = ai_result.get("intent", "unknown")
            processing_path = "ai_primary"
        
        # エンティティのマージ
        merged_entities = {
            **rule_result.get("entities", {}),
            **ai_result.get("entities", {})
        }
        
        return {
            "intent": intent,
            "confidence": merged_confidence,
            "entities": merged_entities,
            "service": rule_result.get("service") or ai_result.get("service"),
            "suggestions": ai_result.get("suggestions", []),
            "processing_path": processing_path,
            "requires_confirmation": merged_confidence < 0.7
        }
    
    async def _resolve_ambiguity(self, result: Dict, original_input: str) -> Dict:
        """曖昧性の解決"""
        suggestions = [
            "どのサービスの操作をお望みですか？（Shopify、Gmail、Stripeなど）",
            "具体的な数値や条件を教えてください",
            "対象となる期間を指定してください（今月、先月、特定の日付など）"
        ]
        
        # エンティティに曖昧表現がある場合の追加質問
        if "ambiguous_terms" in result.get("entities", {}):
            for term in result["entities"]["ambiguous_terms"]:
                if term in self.ambiguity_dict:
                    ambiguity = self.ambiguity_dict[term]
                    if ambiguity["type"] == "relative":
                        suggestions.append(f"「{term}」は具体的にどの程度の変更をお望みですか？")
                    elif ambiguity["type"] == "style":
                        suggestions.append(f"「{term}」のスタイルについて、もう少し詳しく教えてください")
        
        result["suggestions"] = suggestions[:3]  # 最大3つの提案
        result["requires_confirmation"] = True
        
        return result
    
    def _extract_entities(self, text: str) -> Dict:
        """エンティティ抽出"""
        entities = {}
        
        # 日付抽出
        date_patterns = [
            r"(\d{4}[年/-]\d{1,2}[月/-]\d{1,2}日?)",
            r"(今日|昨日|明日|今週|先週|今月|先月|今年|去年)",
            r"(\d{1,2}月\d{1,2}日)"
        ]
        for pattern in date_patterns:
            matches = re.findall(pattern, text)
            if matches:
                entities["date"] = matches[0]
                break
        
        # 数値・金額抽出
        number_patterns = [
            r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*円",
            r"(\d+(?:,\d{3})*)\s*個",
            r"(\d+(?:,\d{3})*)\s*件",
            r"(\d+(?:\.\d+)?)\s*%"
        ]
        for pattern in number_patterns:
            matches = re.findall(pattern, text)
            if matches:
                entities["amount"] = matches[0].replace(",", "")
                break
        
        # メールアドレス抽出
        email_pattern = r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})"
        emails = re.findall(email_pattern, text)
        if emails:
            entities["email"] = emails[0]
        
        # 商品名・タイトル抽出（「」内のテキスト）
        quoted_pattern = r"「([^」]+)」"
        quoted = re.findall(quoted_pattern, text)
        if quoted:
            entities["title"] = quoted[0]
        
        return entities
    
    def _detect_service(self, text: str) -> Optional[str]:
        """サービスの検出"""
        service_keywords = {
            "shopify": ["shopify", "ショッピファイ", "商品", "注文", "在庫", "顧客", "配送"],
            "gmail": ["gmail", "ジーメール", "メール", "送信", "受信", "返信", "転送"],
            "stripe": ["stripe", "ストライプ", "決済", "支払い", "課金", "請求", "サブスク"],
            "slack": ["slack", "スラック", "チャンネル", "メッセージ", "DM", "通知"]
        }
        
        text_lower = text.lower()
        scores = {}
        
        for service, keywords in service_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            if score > 0:
                scores[service] = score
        
        if scores:
            return max(scores, key=scores.get)
        
        return None
    
    def _detect_ambiguous_terms(self, text: str) -> List[str]:
        """曖昧表現の検出"""
        found_terms = []
        for term in self.ambiguity_dict.keys():
            if term in text:
                found_terms.append(term)
        return found_terms
    
    def _generate_cache_key(self, text: str, context: Optional[Dict]) -> str:
        """キャッシュキーの生成"""
        content = f"{text}:{json.dumps(context or {}, sort_keys=True)}"
        return hashlib.md5(content.encode()).hexdigest()
    
    async def refine(self, current_result: AnalysisResult, refinement: str) -> AnalysisResult:
        """結果の精緻化"""
        # 精緻化リクエストを解析
        refinement_analysis = await self.analyze(refinement, {
            "previous_intent": current_result.intent,
            "previous_entities": current_result.entities
        })
        
        # エンティティの更新
        updated_entities = {
            **current_result.entities,
            **refinement_analysis.entities
        }
        
        # 新しい結果を作成
        return AnalysisResult(
            intent=refinement_analysis.intent if refinement_analysis.confidence > 0.7 else current_result.intent,
            confidence=max(current_result.confidence, refinement_analysis.confidence),
            entities=updated_entities,
            service=refinement_analysis.service or current_result.service,
            requires_confirmation=False,
            suggestions=[],
            processing_path="refined",
            processing_time_ms=refinement_analysis.processing_time_ms
        )