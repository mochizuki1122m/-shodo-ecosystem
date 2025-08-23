"""
Perfect MCP Engine - 完璧なModel Context Protocolエコシステム
全ての制約を克服し、あらゆるSaaSに自動接続可能な究極のシステム
"""

import asyncio
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import structlog
from datetime import datetime

# External dependencies
import httpx
import cv2
import numpy as np
from bs4 import BeautifulSoup

logger = structlog.get_logger()

class MCPCapabilityLevel(Enum):
    """MCP機能レベル"""
    BASIC = "basic"                    # 基本CRUD操作
    ADVANCED = "advanced"              # 複雑なワークフロー
    EXPERT = "expert"                  # AI駆動自動化
    MASTER = "master"                  # 完全自律システム

class MCPConnectionStrategy(Enum):
    """MCP接続戦略"""
    OFFICIAL_API = "official_api"              # 公式API
    PARTNERSHIP = "partnership"               # パートナーシップ
    REVERSE_ENGINEERED = "reverse_engineered" # リバースエンジニアリング
    BROWSER_AUTOMATION = "browser_automation" # ブラウザ自動化
    HYBRID_APPROACH = "hybrid_approach"       # ハイブリッド
    AI_DRIVEN = "ai_driven"                   # AI駆動

@dataclass
class MCPServiceProfile:
    """MCPサービスプロファイル"""
    service_name: str
    base_url: str
    service_type: str
    complexity_score: float  # 0.0-1.0
    legal_compliance_level: str
    ethical_requirements: Dict[str, Any]
    technical_constraints: Dict[str, Any]
    business_value: float  # 0.0-1.0
    integration_priority: int  # 1-10
    
    # 動的属性
    connection_strategies: List[MCPConnectionStrategy] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.now)

@dataclass
class MCPOperationResult:
    """MCP操作結果"""
    success: bool
    operation_id: str
    service_name: str
    operation_type: str
    data: Optional[Any] = None
    error: Optional[str] = None
    execution_time_ms: float = 0
    strategy_used: Optional[MCPConnectionStrategy] = None
    confidence_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式への変換"""
        return {
            "success": self.success,
            "operation_id": self.operation_id,
            "service_name": self.service_name,
            "operation_type": self.operation_type,
            "data": self.data,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "strategy_used": self.strategy_used.value if self.strategy_used else None,
            "confidence_score": self.confidence_score,
            "metadata": self.metadata
        }

class PerfectLegalComplianceEngine:
    """完璧な法的コンプライアンスエンジン"""
    
    def __init__(self, llm_client):
        self.llm_client = llm_client
        self.compliance_cache = {}
        self.legal_knowledge_base = {}
        self.update_lock = asyncio.Lock()
        
    async def analyze_service_legality(
        self, 
        service_profile: MCPServiceProfile,
        intended_operations: List[str]
    ) -> Dict[str, Any]:
        """サービスの法的分析"""
        
        cache_key = f"{service_profile.service_name}:{hash(tuple(intended_operations))}"
        
        async with self.update_lock:
            if cache_key in self.compliance_cache:
                cached_result = self.compliance_cache[cache_key]
                if (datetime.now() - cached_result["timestamp"]).hours < 24:
                    return cached_result["analysis"]
        
        # 利用規約の動的取得・解析
        terms_analysis = await self._extract_and_analyze_terms(service_profile.base_url)
        
        # GPT-OSS-20による法的分析
        legal_analysis = await self._perform_llm_legal_analysis(
            service_profile, terms_analysis, intended_operations
        )
        
        # 代替戦略の生成
        if legal_analysis["compliance_level"] != "fully_compliant":
            alternatives = await self._generate_legal_alternatives(
                service_profile, legal_analysis, intended_operations
            )
            legal_analysis["alternatives"] = alternatives
        
        # キャッシュ更新
        async with self.update_lock:
            self.compliance_cache[cache_key] = {
                "analysis": legal_analysis,
                "timestamp": datetime.now()
            }
        
        return legal_analysis
    
    async def _extract_and_analyze_terms(self, base_url: str) -> Dict[str, Any]:
        """利用規約の抽出・解析"""
        
        terms_urls = [
            f"{base_url}/terms",
            f"{base_url}/terms-of-service",
            f"{base_url}/legal/terms",
            f"{base_url}/api/terms",
            f"{base_url}/developers/terms",
            f"{base_url}/robots.txt"
        ]
        
        extracted_terms = {}
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            for url in terms_urls:
                try:
                    response = await client.get(url)
                    if response.status_code == 200:
                        content = response.text
                        
                        # コンテンツタイプに基づく分類
                        if "robots.txt" in url:
                            extracted_terms["robots_txt"] = content
                        elif any(keyword in url for keyword in ["api", "dev"]):
                            extracted_terms["api_terms"] = content
                        else:
                            extracted_terms["general_terms"] = content
                            
                except Exception as e:
                    logger.debug(f"Failed to fetch terms from {url}: {e}")
                    continue
        
        return extracted_terms
    
    async def _perform_llm_legal_analysis(
        self,
        service_profile: MCPServiceProfile,
        terms_analysis: Dict[str, Any],
        intended_operations: List[str]
    ) -> Dict[str, Any]:
        """LLMによる法的分析"""
        
        analysis_prompt = f"""
あなたは国際的な法的コンプライアンスの専門家です。
以下のサービスと操作について、包括的な法的分析を行ってください。

サービス情報:
- 名前: {service_profile.service_name}
- URL: {service_profile.base_url}
- タイプ: {service_profile.service_type}

予定操作: {', '.join(intended_operations)}

利用規約データ:
{json.dumps(terms_analysis, ensure_ascii=False, indent=2)}

以下の観点で詳細分析してください:
1. 自動化・ボット使用の許可/禁止
2. API利用に関する規定
3. データ取得・処理の制限
4. レート制限・技術的制約
5. 商用利用の可否
6. 第三者アクセスの規定
7. データ保護・プライバシー要件
8. 国際的な法的要件（GDPR、CCPA等）

結果をJSON形式で返してください:
{{
    "compliance_level": "fully_compliant|conditionally_compliant|requires_permission|prohibited",
    "legal_score": 0.0-1.0の数値,
    "allowed_operations": ["許可された操作のリスト"],
    "prohibited_operations": ["禁止された操作のリスト"],
    "conditional_operations": [
        {{"operation": "操作名", "conditions": ["条件のリスト"]}}
    ],
    "rate_limits": {{
        "requests_per_minute": 数値または null,
        "requests_per_hour": 数値または null,
        "daily_limits": 数値または null
    }},
    "required_permissions": ["必要な許可のリスト"],
    "attribution_requirements": ["帰属表示要件"],
    "data_protection_requirements": ["データ保護要件"],
    "geographic_restrictions": ["地理的制限"],
    "legal_reasoning": "詳細な法的根拠",
    "risk_assessment": {{
        "legal_risk_level": "low|medium|high|critical",
        "potential_consequences": ["潜在的結果のリスト"],
        "mitigation_strategies": ["リスク軽減策"]
    }},
    "monitoring_requirements": ["必要な監視項目"],
    "compliance_checklist": ["コンプライアンス確認項目"]
}}
"""
        
        try:
            response = await self.llm_client.chat.completions.create(
                model="gpt-oss-20b",
                messages=[
                    {
                        "role": "system", 
                        "content": "あなたは国際法、データ保護法、技術法に精通した法的コンプライアンスの専門家です。正確で実用的な法的分析を提供してください。"
                    },
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=0.1,
                max_tokens=3000
            )
            
            analysis_text = response.choices[0].message.content
            
            # JSON抽出
            import re
            json_match = re.search(r'\{.*\}', analysis_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
                
        except Exception as e:
            logger.error(f"LLM legal analysis failed: {e}")
        
        # フォールバック分析
        return {
            "compliance_level": "requires_permission",
            "legal_score": 0.5,
            "allowed_operations": ["official_api_usage"],
            "prohibited_operations": ["unlimited_scraping"],
            "rate_limits": {"requests_per_minute": 60, "requests_per_hour": 1000},
            "legal_reasoning": "詳細な法的分析が必要",
            "risk_assessment": {"legal_risk_level": "medium"}
        }
    
    async def _generate_legal_alternatives(
        self,
        service_profile: MCPServiceProfile,
        legal_analysis: Dict[str, Any],
        intended_operations: List[str]
    ) -> List[Dict[str, Any]]:
        """合法的代替手段の生成"""
        
        alternatives_prompt = f"""
サービス「{service_profile.service_name}」で以下の操作を合法的に実現する代替方法を提案してください。

目標操作: {', '.join(intended_operations)}
法的制約: {legal_analysis.get('legal_reasoning', '')}
禁止事項: {', '.join(legal_analysis.get('prohibited_operations', []))}

以下の代替アプローチを検討してください:
1. 公式API・パートナーシップの活用
2. 利用規約準拠の自動化
3. 手動プロセスの効率化
4. 第三者サービス・プロキシの活用
5. オープンデータ・代替データソースの活用
6. 段階的アプローチ（許可取得→実装）

各代替案について、以下のJSON形式で提案してください:
[
    {{
        "approach_name": "アプローチ名",
        "description": "詳細説明",
        "implementation_steps": ["実装ステップのリスト"],
        "legal_compliance": "full|partial|conditional",
        "feasibility_score": 0.0-1.0の数値,
        "estimated_effort": "low|medium|high",
        "expected_success_rate": 0.0-1.0の数値,
        "required_resources": ["必要リソース"],
        "timeline": "予想期間",
        "pros": ["利点のリスト"],
        "cons": ["欠点のリスト"]
    }}
]
"""
        
        try:
            response = await self.llm_client.chat.completions.create(
                model="gpt-oss-20b",
                messages=[
                    {
                        "role": "system",
                        "content": "あなたは技術と法律の両方に精通し、実用的な解決策を提供する専門家です。"
                    },
                    {"role": "user", "content": alternatives_prompt}
                ],
                temperature=0.3,
                max_tokens=2500
            )
            
            alternatives_text = response.choices[0].message.content
            
            # JSON配列の抽出
            import re
            json_match = re.search(r'\[.*\]', alternatives_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
                
        except Exception as e:
            logger.error(f"Alternatives generation failed: {e}")
        
        # フォールバック代替案
        return [
            {
                "approach_name": "公式API利用",
                "description": "公式APIの利用申請・実装",
                "legal_compliance": "full",
                "feasibility_score": 0.8,
                "estimated_effort": "medium"
            },
            {
                "approach_name": "パートナーシップ締結",
                "description": "公式パートナーシップの締結",
                "legal_compliance": "full",
                "feasibility_score": 0.6,
                "estimated_effort": "high"
            }
        ]

class PerfectPatternRecognitionEngine:
    """完璧なパターン認識エンジン"""
    
    def __init__(self, llm_client):
        self.llm_client = llm_client
        self.pattern_cache = {}
        self.ai_models = {}
        self.learning_data = []
        
    async def initialize_ai_models(self):
        """AI モデルの初期化"""
        try:
            # UI要素認識モデル（Computer Vision）
            self.ui_model = await self._load_ui_recognition_model()
            
            # テキスト分析モデル（NLP）
            self.text_model = await self._load_text_analysis_model()
            
            # 行動パターン学習モデル
            self.behavior_model = await self._load_behavior_learning_model()
            
            logger.info("AI models initialized successfully")
            
        except Exception as e:
            logger.warning(f"AI model initialization failed: {e}")
            # フォールバック: ルールベース認識
            await self._initialize_fallback_models()
    
    async def _load_ui_recognition_model(self):
        """UI認識モデルの読み込み"""
        # 実装: YOLO、Detectron2、またはカスタムCNNモデル
        class UIRecognitionModel:
            async def detect_elements(self, image: np.ndarray) -> List[Dict[str, Any]]:
                """UI要素の検出"""
                # OpenCVベースの基本的な要素検出
                elements = []
                
                # ボタン検出（色・形状ベース）
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                
                # エッジ検出
                edges = cv2.Canny(gray, 50, 150)
                contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                for contour in contours:
                    area = cv2.contourArea(contour)
                    if 100 < area < 10000:  # ボタンサイズの範囲
                        x, y, w, h = cv2.boundingRect(contour)
                        elements.append({
                            "type": "button",
                            "bbox": {"x": x, "y": y, "width": w, "height": h},
                            "confidence": 0.7
                        })
                
                return elements
        
        return UIRecognitionModel()
    
    async def _load_text_analysis_model(self):
        """テキスト分析モデルの読み込み"""
        class TextAnalysisModel:
            def __init__(self, llm_client):
                self.llm_client = llm_client
            
            async def analyze_text_intent(self, text: str) -> Dict[str, Any]:
                """テキストの意図分析"""
                
                intent_prompt = f"""
以下のテキストから、UI要素の種類と機能を分析してください:

テキスト: "{text}"

以下のJSON形式で結果を返してください:
{{
    "element_type": "button|input|link|label|heading|other",
    "primary_function": "create|read|update|delete|search|navigate|submit|cancel|other",
    "confidence": 0.0-1.0の数値,
    "keywords": ["関連キーワードのリスト"],
    "user_action": "予想されるユーザーアクション"
}}
"""
                
                try:
                    response = await self.llm_client.chat.completions.create(
                        model="gpt-oss-20b",
                        messages=[
                            {"role": "system", "content": "あなたはUI/UX分析の専門家です。"},
                            {"role": "user", "content": intent_prompt}
                        ],
                        temperature=0.1,
                        max_tokens=500
                    )
                    
                    analysis_text = response.choices[0].message.content
                    
                    import re
                    json_match = re.search(r'\{.*\}', analysis_text, re.DOTALL)
                    if json_match:
                        return json.loads(json_match.group())
                        
                except Exception as e:
                    logger.error(f"Text intent analysis failed: {e}")
                
                # フォールバック分析
                return {
                    "element_type": "other",
                    "primary_function": "other",
                    "confidence": 0.5,
                    "keywords": text.split()[:5],
                    "user_action": "unknown"
                }
        
        return TextAnalysisModel(self.llm_client)
    
    async def _load_behavior_learning_model(self):
        """行動学習モデルの読み込み"""
        class BehaviorLearningModel:
            def __init__(self):
                self.interaction_patterns = {}
                self.success_patterns = {}
            
            async def learn_from_interaction(
                self, 
                service_name: str,
                interaction_data: Dict[str, Any],
                success: bool
            ):
                """相互作用からの学習"""
                
                if service_name not in self.interaction_patterns:
                    self.interaction_patterns[service_name] = []
                    self.success_patterns[service_name] = []
                
                self.interaction_patterns[service_name].append(interaction_data)
                self.success_patterns[service_name].append(success)
                
                # パターンの最適化（簡易実装）
                if len(self.interaction_patterns[service_name]) > 100:
                    # 成功率の高いパターンを保持
                    successful_patterns = [
                        pattern for pattern, success in 
                        zip(self.interaction_patterns[service_name], self.success_patterns[service_name])
                        if success
                    ]
                    
                    self.interaction_patterns[service_name] = successful_patterns[-50:]
                    self.success_patterns[service_name] = [True] * len(successful_patterns[-50:])
            
            async def predict_best_approach(self, service_name: str, context: Dict[str, Any]) -> Dict[str, Any]:
                """最適アプローチの予測"""
                
                if service_name not in self.interaction_patterns:
                    return {"confidence": 0.0, "recommended_approach": "exploratory"}
                
                # 類似コンテキストの検索（簡易実装）
                similar_patterns = []
                for pattern in self.interaction_patterns[service_name]:
                    similarity = self._calculate_context_similarity(context, pattern.get("context", {}))
                    if similarity > 0.7:
                        similar_patterns.append(pattern)
                
                if similar_patterns:
                    # 最も成功率の高いアプローチを推奨
                    best_pattern = max(similar_patterns, key=lambda p: p.get("success_rate", 0))
                    return {
                        "confidence": best_pattern.get("success_rate", 0.5),
                        "recommended_approach": best_pattern.get("approach", "standard"),
                        "estimated_success_rate": best_pattern.get("success_rate", 0.5)
                    }
                
                return {"confidence": 0.3, "recommended_approach": "standard"}
            
            def _calculate_context_similarity(self, context1: Dict, context2: Dict) -> float:
                """コンテキスト類似度の計算"""
                
                if not context1 or not context2:
                    return 0.0
                
                common_keys = set(context1.keys()) & set(context2.keys())
                if not common_keys:
                    return 0.0
                
                similarities = []
                for key in common_keys:
                    val1, val2 = context1[key], context2[key]
                    if val1 == val2:
                        similarities.append(1.0)
                    elif isinstance(val1, str) and isinstance(val2, str):
                        # 文字列の類似度（簡易実装）
                        similarity = len(set(val1.split()) & set(val2.split())) / max(len(val1.split()), len(val2.split()), 1)
                        similarities.append(similarity)
                    else:
                        similarities.append(0.0)
                
                return sum(similarities) / len(similarities) if similarities else 0.0
        
        return BehaviorLearningModel()
    
    async def analyze_service_patterns(
        self,
        service_profile: MCPServiceProfile,
        page_content: Dict[str, Any]
    ) -> Dict[str, Any]:
        """サービスパターンの包括的分析"""
        
        analysis_results = {
            "ui_patterns": [],
            "data_patterns": [],
            "interaction_patterns": [],
            "authentication_patterns": [],
            "navigation_patterns": [],
            "content_patterns": []
        }
        
        # 並列分析の実行
        analysis_tasks = [
            self._analyze_ui_patterns(page_content),
            self._analyze_data_patterns(page_content),
            self._analyze_authentication_patterns(page_content),
            self._analyze_navigation_patterns(page_content),
            self._analyze_content_patterns(page_content)
        ]
        
        results = await asyncio.gather(*analysis_tasks, return_exceptions=True)
        
        # 結果の統合
        pattern_types = ["ui_patterns", "data_patterns", "authentication_patterns", "navigation_patterns", "content_patterns"]
        
        for i, result in enumerate(results):
            if not isinstance(result, Exception) and i < len(pattern_types):
                analysis_results[pattern_types[i]] = result
        
        # 相互作用パターンの分析
        analysis_results["interaction_patterns"] = await self._analyze_interaction_patterns(analysis_results)
        
        # 学習データへの追加
        await self._add_to_learning_data(service_profile.service_name, analysis_results)
        
        return analysis_results
    
    async def _analyze_ui_patterns(self, page_content: Dict[str, Any]) -> List[Dict[str, Any]]:
        """UI パターンの分析"""
        
        ui_patterns = []
        
        # HTML構造の分析
        if "html" in page_content:
            html_patterns = await self._analyze_html_structure(page_content["html"])
            ui_patterns.extend(html_patterns)
        
        # 視覚的分析（スクリーンショットがある場合）
        if "screenshot" in page_content:
            visual_patterns = await self._analyze_visual_elements(page_content["screenshot"])
            ui_patterns.extend(visual_patterns)
        
        # CSS分析
        if "css" in page_content:
            css_patterns = await self._analyze_css_patterns(page_content["css"])
            ui_patterns.extend(css_patterns)
        
        return ui_patterns
    
    async def _analyze_html_structure(self, html_content: str) -> List[Dict[str, Any]]:
        """HTML構造の詳細分析"""
        
        patterns = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # フォーム分析
            forms = soup.find_all('form')
            for i, form in enumerate(forms):
                form_analysis = await self._analyze_form_structure(form, i)
                patterns.append(form_analysis)
            
            # テーブル分析
            tables = soup.find_all('table')
            for i, table in enumerate(tables):
                table_analysis = await self._analyze_table_structure(table, i)
                patterns.append(table_analysis)
            
            # ナビゲーション分析
            navs = soup.find_all(['nav', 'ul', 'ol'])
            for i, nav in enumerate(navs):
                nav_analysis = await self._analyze_navigation_structure(nav, i)
                patterns.append(nav_analysis)
            
            # ボタン・リンク分析
            interactive_elements = soup.find_all(['button', 'a', 'input'])
            for i, element in enumerate(interactive_elements):
                element_analysis = await self._analyze_interactive_element(element, i)
                patterns.append(element_analysis)
            
        except Exception as e:
            logger.error(f"HTML structure analysis failed: {e}")
        
        return patterns
    
    async def _analyze_form_structure(self, form_element, index: int) -> Dict[str, Any]:
        """フォーム構造の分析"""
        
        fields = []
        for form_field in form_element.find_all(['input', 'select', 'textarea']):
            field_info = {
                "type": form_field.get('type', form_field.name),
                "name": form_field.get('name', ''),
                "id": form_field.get('id', ''),
                "required": form_field.has_attr('required'),
                "placeholder": form_field.get('placeholder', ''),
                "value": form_field.get('value', '')
            }
            
            # フィールドの意図分析
            field_text = f"{field_info['name']} {field_info['placeholder']} {field_info['id']}"
            if self.text_model:
                intent_analysis = await self.text_model.analyze_text_intent(field_text)
                field_info["intent"] = intent_analysis
            
            fields.append(field_info)
        
        return {
            "pattern_type": "form",
            "index": index,
            "action": form_element.get('action', ''),
            "method": form_element.get('method', 'GET'),
            "fields": fields,
            "field_count": len(fields),
            "has_file_upload": any(f["type"] == "file" for f in fields),
            "has_password": any(f["type"] == "password" for f in fields),
            "submit_buttons": len(form_element.find_all(['input[type="submit"]', 'button[type="submit"]'])),
            "css_selector": self._generate_css_selector(form_element)
        }
    
    async def _analyze_table_structure(self, table_element, index: int) -> Dict[str, Any]:
        """テーブル構造の分析"""
        
        headers = []
        header_elements = table_element.find_all('th')
        for th in header_elements:
            header_text = th.get_text(strip=True)
            headers.append({
                "text": header_text,
                "sortable": bool(th.find(['a', 'button']) or 'sort' in th.get('class', [])),
                "data_type": await self._infer_data_type(header_text)
            })
        
        # データ行の分析
        rows = table_element.find_all('tr')
        data_rows = [row for row in rows if not row.find('th')]
        
        return {
            "pattern_type": "table",
            "index": index,
            "headers": headers,
            "header_count": len(headers),
            "row_count": len(data_rows),
            "has_pagination": bool(table_element.find_parent().find(['nav', 'div'], class_=lambda x: x and 'pag' in x.lower())),
            "has_sorting": any(h["sortable"] for h in headers),
            "estimated_data_type": await self._infer_table_data_type(headers),
            "css_selector": self._generate_css_selector(table_element)
        }
    
    async def _infer_data_type(self, text: str) -> str:
        """データ型の推論"""
        
        text_lower = text.lower()
        
        if any(keyword in text_lower for keyword in ['id', 'identifier', '識別']):
            return "id"
        elif any(keyword in text_lower for keyword in ['name', 'title', '名前', 'タイトル']):
            return "text"
        elif any(keyword in text_lower for keyword in ['date', 'time', '日付', '時間']):
            return "datetime"
        elif any(keyword in text_lower for keyword in ['price', 'cost', 'amount', '価格', '金額']):
            return "currency"
        elif any(keyword in text_lower for keyword in ['count', 'number', 'quantity', '数量', '個数']):
            return "number"
        elif any(keyword in text_lower for keyword in ['status', 'state', 'condition', 'ステータス', '状態']):
            return "status"
        else:
            return "text"
    
    async def _infer_table_data_type(self, headers: List[Dict[str, Any]]) -> str:
        """テーブルデータ型の推論"""
        
        data_types = [h["data_type"] for h in headers]
        
        if "id" in data_types and any(dt in data_types for dt in ["text", "datetime"]):
            if any(keyword in str(headers).lower() for keyword in ['product', 'item', 'inventory', '商品', '在庫']):
                return "inventory"
            elif any(keyword in str(headers).lower() for keyword in ['user', 'customer', 'member', 'ユーザー', '顧客']):
                return "user_data"
            elif any(keyword in str(headers).lower() for keyword in ['order', 'transaction', 'purchase', '注文', '取引']):
                return "transaction"
            else:
                return "entity_list"
        else:
            return "general_data"
    
    def _generate_css_selector(self, element) -> str:
        """CSS セレクタの生成"""
        
        # ID優先
        if element.get('id'):
            return f"#{element['id']}"
        
        # クラス
        if element.get('class'):
            classes = element['class'] if isinstance(element['class'], list) else [element['class']]
            return f".{'.'.join(classes)}"
        
        # 要素名 + 属性
        selector = element.name
        if element.get('name'):
            selector += f"[name='{element['name']}']"
        elif element.get('type'):
            selector += f"[type='{element['type']}']"
        
        return selector

class PerfectProtocolSynthesizer:
    """完璧なプロトコル合成エンジン"""
    
    def __init__(self, llm_client):
        self.llm_client = llm_client
        self.synthesis_cache = {}
        self.optimization_history = {}
        
    async def synthesize_optimal_protocol(
        self,
        service_profile: MCPServiceProfile,
        legal_analysis: Dict[str, Any],
        pattern_analysis: Dict[str, Any],
        business_requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        """最適プロトコルの合成"""
        
        # プロトコル合成のプロンプト生成
        synthesis_prompt = await self._generate_synthesis_prompt(
            service_profile, legal_analysis, pattern_analysis, business_requirements
        )
        
        # GPT-OSS-20による合成
        protocol_specification = await self._synthesize_with_llm(synthesis_prompt)
        
        # 実装コードの生成
        implementation_code = await self._generate_implementation_code(
            service_profile, protocol_specification, pattern_analysis
        )
        
        # 最適化の適用
        optimized_code = await self._optimize_implementation(
            implementation_code, service_profile, business_requirements
        )
        
        # テストケースの生成
        test_cases = await self._generate_test_cases(
            service_profile, protocol_specification, pattern_analysis
        )
        
        return {
            "protocol_specification": protocol_specification,
            "implementation_code": optimized_code,
            "test_cases": test_cases,
            "performance_estimates": await self._estimate_performance(protocol_specification),
            "maintenance_requirements": await self._analyze_maintenance_needs(protocol_specification),
            "scaling_strategy": await self._design_scaling_strategy(protocol_specification)
        }
    
    async def _generate_synthesis_prompt(
        self,
        service_profile: MCPServiceProfile,
        legal_analysis: Dict[str, Any],
        pattern_analysis: Dict[str, Any],
        business_requirements: Dict[str, Any]
    ) -> str:
        """合成プロンプトの生成"""
        
        return f"""
あなたは世界最高のプロトコル設計エンジニアです。
以下の情報を基に、最適なMCPプロトコルを設計してください。

サービス情報:
{json.dumps(service_profile.__dict__, default=str, ensure_ascii=False, indent=2)}

法的分析:
{json.dumps(legal_analysis, ensure_ascii=False, indent=2)}

パターン分析:
{json.dumps(pattern_analysis, ensure_ascii=False, indent=2)}

ビジネス要件:
{json.dumps(business_requirements, ensure_ascii=False, indent=2)}

以下の観点で最適なプロトコルを設計してください:

1. 法的コンプライアンス
2. 技術的実現可能性
3. パフォーマンス効率
4. 保守性・拡張性
5. エラー処理・回復
6. セキュリティ
7. 監視・ログ
8. コスト効率

プロトコル仕様をJSON形式で返してください:
{{
    "protocol_name": "プロトコル名",
    "version": "バージョン",
    "strategy": "primary_strategy",
    "fallback_strategies": ["フォールバック戦略のリスト"],
    "authentication": {{
        "method": "認証方式",
        "parameters": {{}},
        "fallback_methods": []
    }},
    "operations": [
        {{
            "name": "操作名",
            "method": "実行方式",
            "parameters": {{}},
            "success_criteria": [],
            "error_handling": {{}},
            "rate_limiting": {{}},
            "caching_strategy": {{}}
        }}
    ],
    "data_transformation": {{
        "input_mapping": {{}},
        "output_mapping": {{}},
        "validation_rules": []
    }},
    "monitoring": {{
        "metrics": [],
        "alerts": [],
        "logging_level": "INFO"
    }},
    "performance_targets": {{
        "response_time_ms": 1000,
        "success_rate": 0.99,
        "throughput_rps": 10
    }},
    "scaling_parameters": {{
        "max_concurrent_operations": 5,
        "queue_size": 100,
        "timeout_ms": 30000
    }}
}}
"""
    
    async def _synthesize_with_llm(self, synthesis_prompt: str) -> Dict[str, Any]:
        """LLMによるプロトコル合成"""
        
        try:
            response = await self.llm_client.chat.completions.create(
                model="gpt-oss-20b",
                messages=[
                    {
                        "role": "system",
                        "content": "あなたは分散システム、プロトコル設計、法的コンプライアンスのエキスパートです。最適で実用的なプロトコルを設計してください。"
                    },
                    {"role": "user", "content": synthesis_prompt}
                ],
                temperature=0.2,
                max_tokens=4000
            )
            
            synthesis_text = response.choices[0].message.content
            
            # JSON抽出
            import re
            json_match = re.search(r'\{.*\}', synthesis_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
                
        except Exception as e:
            logger.error(f"Protocol synthesis failed: {e}")
        
        # フォールバック仕様
        return {
            "protocol_name": "StandardMCPProtocol",
            "version": "1.0",
            "strategy": "browser_automation",
            "authentication": {"method": "form_based"},
            "operations": [
                {"name": "list_items", "method": "table_extraction"},
                {"name": "create_item", "method": "form_submission"}
            ]
        }

# 続く...（次のメッセージで残りの実装を続けます）