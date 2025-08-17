# 📘 **shodo ecosystem 完全仕様書兼開発書 v5.0**
## **GPT-OSS統合版 - 実装詳細仕様**

---

## **目次**
1. [システム概要](#1-システム概要)
2. [機能詳細仕様](#2-機能詳細仕様)
3. [技術アーキテクチャ](#3-技術アーキテクチャ)
4. [実装仕様](#4-実装仕様)
5. [インフラ構成](#5-インフラ構成)
6. [開発手順書](#6-開発手順書)
7. [テスト仕様](#7-テスト仕様)
8. [運用仕様](#8-運用仕様)

---

## **1. システム概要**

### **1.1 システムの目的と価値**

```yaml
システム名: shodo ecosystem
バージョン: 5.0
リリース予定: 2025年3月

目的:
  主要: 非技術者が自然言語（日本語）でSaaSを安全に操作できる統合プラットフォーム
  副次: APIコストを97.5%削減しながら15倍の高速化を実現

価値提案:
  コスト面:
    - 月額費用: 200万円 → 5万円（97.5%削減）
    - 初期投資回収: 1ヶ月
    - 年間削減額: 2,340万円
    
  性能面:
    - レスポンス: 3秒 → 0.2秒（15倍高速）
    - 同時処理: 1 → 50ユーザー
    - 月間処理量: 10万 → 100万リクエスト
    
  セキュリティ面:
    - データ漏洩リスク: ゼロ（完全ローカル処理）
    - コンプライアンス: GDPR/個人情報保護法準拠
    - 監査証跡: 完全記録

対象ユーザー:
  - EC事業者（Shopify運営者）
  - マーケティング担当者
  - カスタマーサポート
  - 中小企業経営者
  - フリーランス
```

### **1.2 システム構成要素**

| レイヤー | コンポーネント | 技術スタック | 役割 |
|---------|--------------|-------------|------|
| **AI層** | GPT-OSS推論エンジン | GPT-OSS-20B, vLLM | 自然言語理解・生成 |
| **UI層** | Webアプリケーション | React 18, TypeScript 5 | ユーザーインターフェース |
| **処理層** | NLPサービス | 二重経路解析, Python | 意図解析・曖昧性解決 |
| **認証層** | LPRマネージャー | JWS, TPM 2.0 | セキュア認証管理 |
| **統合層** | MCPサーバー | JSON-RPC 2.0 | ツール標準化 |
| **実行層** | User-Agent | Playwright, CDP | ブラウザ自動化 |
| **データ層** | 永続化 | PostgreSQL, Redis | データ管理・キャッシュ |

---

## **2. 機能詳細仕様**

### **2.1 自然言語処理機能**

#### **2.1.1 二重経路解析エンジン**

```typescript
interface DualPathAnalysisEngine {
  // 機能ID: F-NLP-001
  // 優先度: Critical
  // 依存: GPT-OSS-20B, ルールエンジン
  
  configuration: {
    // ルールベース設定
    ruleEngine: {
      patterns: RegExpPattern[];      // 1000+パターン定義
      confidence_threshold: 0.8;      // 確信度閾値
      processing_time_ms: 10;         // 目標処理時間
      cache_ttl_seconds: 3600;        // キャッシュ有効期限
    };
    
    // AI解析設定
    aiEngine: {
      model: 'gpt-oss-20b';           // 使用モデル
      temperature: 0.3;                // 生成の確定性
      max_tokens: 2048;                // 最大トークン数
      context_window: 128000;          // コンテキストウィンドウ
      quantization: 'INT4';            // 量子化レベル
    };
    
    // 統合設定
    merger: {
      rule_weight: 0.4;                // ルールベースの重み
      ai_weight: 0.6;                  // AI解析の重み
      conflict_resolution: 'ai_first'; // 競合解決方針
    };
  };
  
  // 主要メソッド
  analyze(input: UserInput): Promise<AnalysisResult>;
  refine(result: AnalysisResult, feedback: UserFeedback): Promise<RefinedResult>;
  learn(session: AnalysisSession): Promise<void>;
}
```

##### **実装詳細**

```python
# backend/src/services/nlp/dual_path_engine.py
import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass
import numpy as np

@dataclass
class AnalysisResult:
    intent: str                    # 操作意図
    confidence: float              # 確信度 (0.0-1.0)
    entities: Dict[str, any]       # 抽出エンティティ
    service: str                   # 対象サービス
    requires_confirmation: bool    # 確認要否
    suggestions: List[str]         # 改善提案
    processing_path: str           # 'rule' | 'ai' | 'merged'

class DualPathEngine:
    """二重経路解析エンジン"""
    
    def __init__(self, config: Dict):
        self.rule_engine = RuleBasedAnalyzer(config['rule_engine'])
        self.ai_engine = GPTOSSAnalyzer(config['ai_engine'])
        self.merger = ResultMerger(config['merger'])
        self.cache = AnalysisCache()
        
    async def analyze(self, input_text: str, context: Optional[Dict] = None) -> AnalysisResult:
        """
        入力テキストを二重経路で解析
        
        処理フロー:
        1. キャッシュチェック
        2. 前処理（正規化）
        3. 並列解析（ルール + AI）
        4. 結果統合
        5. 曖昧性解決
        6. キャッシュ保存
        """
        
        # キャッシュチェック
        cache_key = self._generate_cache_key(input_text, context)
        cached = await self.cache.get(cache_key)
        if cached:
            return cached
            
        # 前処理
        normalized = self._normalize_input(input_text)
        
        # 並列解析
        rule_task = asyncio.create_task(
            self.rule_engine.analyze(normalized, context)
        )
        ai_task = asyncio.create_task(
            self.ai_engine.analyze(normalized, context)
        )
        
        rule_result, ai_result = await asyncio.gather(rule_task, ai_task)
        
        # 結果統合
        merged_result = self.merger.merge(rule_result, ai_result)
        
        # 曖昧性解決
        if merged_result.confidence < 0.7:
            merged_result = await self._resolve_ambiguity(merged_result, input_text)
            
        # キャッシュ保存
        await self.cache.set(cache_key, merged_result)
        
        return merged_result
    
    def _normalize_input(self, text: str) -> str:
        """入力正規化"""
        # 全角→半角変換
        text = text.translate(str.maketrans(
            '０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ',
            '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
        ))
        
        # 空白正規化
        text = ' '.join(text.split())
        
        return text
    
    async def _resolve_ambiguity(self, result: AnalysisResult, original_input: str) -> AnalysisResult:
        """曖昧性解決"""
        
        # GPT-OSSを使った詳細化
        clarification_prompt = f"""
        ユーザー入力: {original_input}
        
        現在の解析結果:
        - 意図: {result.intent}
        - 確信度: {result.confidence}
        - エンティティ: {result.entities}
        
        この入力の曖昧な部分を特定し、明確化するための質問を3つ生成してください。
        """
        
        suggestions = await self.ai_engine.generate_clarifications(clarification_prompt)
        result.suggestions = suggestions
        result.requires_confirmation = True
        
        return result
```

#### **2.1.2 日本語特化処理**

```python
class JapaneseLanguageProcessor:
    """
    機能ID: F-NLP-002
    日本語特有の表現を高精度で処理
    """
    
    def __init__(self):
        # 日本語特化トークナイザー（40-60%効率化）
        self.tokenizer = AutoTokenizer.from_pretrained(
            "RakutenAI/rakutenai-7b",
            additional_special_tokens=['<価格>', '<日付>', '<商品名>']
        )
        
        # 曖昧表現辞書
        self.ambiguity_dict = {
            'もっと': {'type': 'relative', 'default_ratio': 1.2},
            '少し': {'type': 'relative', 'default_ratio': 1.1},
            'かなり': {'type': 'relative', 'default_ratio': 1.5},
            '大幅に': {'type': 'relative', 'default_ratio': 2.0},
            '目立つ': {'type': 'style', 'attributes': ['bold', 'large', 'colorful']},
            '控えめ': {'type': 'style', 'attributes': ['small', 'muted', 'simple']}
        }
        
    def process(self, text: str) -> ProcessedText:
        """
        処理フロー:
        1. 形態素解析
        2. 係り受け解析
        3. 曖昧表現の具体化
        4. エンティティ抽出
        """
        
        # 形態素解析
        tokens = self.tokenizer.tokenize(text)
        
        # 曖昧表現の検出と具体化
        concrete_values = self._concretize_ambiguous_expressions(tokens)
        
        # エンティティ抽出
        entities = self._extract_entities(tokens)
        
        return ProcessedText(
            original=text,
            tokens=tokens,
            concrete_values=concrete_values,
            entities=entities
        )
    
    def _concretize_ambiguous_expressions(self, tokens: List[str]) -> Dict:
        """
        曖昧表現を具体的な値に変換
        
        例:
        - "価格をもっと安く" → {'action': 'decrease', 'target': 'price', 'ratio': 0.8}
        - "少し大きく" → {'action': 'increase', 'target': 'size', 'ratio': 1.1}
        """
        concrete = {}
        
        for i, token in enumerate(tokens):
            if token in self.ambiguity_dict:
                ambiguity = self.ambiguity_dict[token]
                
                # 前後の文脈から対象を特定
                target = self._identify_target(tokens, i)
                
                if ambiguity['type'] == 'relative':
                    concrete[target] = {
                        'action': self._determine_action(tokens, i),
                        'ratio': ambiguity['default_ratio']
                    }
                elif ambiguity['type'] == 'style':
                    concrete[target] = {
                        'attributes': ambiguity['attributes']
                    }
                    
        return concrete
```

### **2.2 プレビュー・反復修正機能**

#### **2.2.1 サンドボックスプレビューエンジン**

```typescript
interface PreviewEngine {
  // 機能ID: F-PREVIEW-001
  // 優先度: Critical
  // 特徴: 無限の修正サイクル、本番環境に影響なし
  
  capabilities: {
    max_iterations: number;           // 無制限 (実質100回まで)
    preview_generation_time_ms: 500;  // プレビュー生成時間
    diff_calculation: boolean;        // 差分計算機能
    visual_comparison: boolean;       // ビジュアル比較
    version_control: boolean;         // バージョン管理
    rollback: boolean;               // ロールバック機能
  };
  
  // コア機能
  generatePreview(changes: Change[]): Promise<Preview>;
  refinePreview(preview: Preview, refinement: string): Promise<Preview>;
  applyToProduction(preview: Preview): Promise<ApplyResult>;
  rollback(version: string): Promise<RollbackResult>;
}
```

##### **実装詳細**

```python
# backend/src/services/preview/sandbox_engine.py
import asyncio
import hashlib
from datetime import datetime
from typing import List, Dict, Optional
import json

class SandboxPreviewEngine:
    """
    サンドボックス環境でプレビューを生成・管理
    """
    
    def __init__(self, config: Dict):
        self.sandbox = VirtualEnvironment(config['sandbox'])
        self.version_control = VersionControl()
        self.diff_calculator = DiffCalculator()
        self.visual_renderer = VisualRenderer()
        
    async def generate_preview(self, changes: List[Change], context: Dict) -> Preview:
        """
        プレビュー生成
        
        処理内容:
        1. 現在状態のスナップショット
        2. 仮想環境での変更適用
        3. ビジュアルレンダリング
        4. 差分計算
        5. プレビューオブジェクト生成
        """
        
        # 現在状態をキャプチャ
        current_state = await self.sandbox.capture_current_state(context['service_id'])
        
        # 仮想環境を初期化
        virtual_env = await self.sandbox.create_virtual_copy(current_state)
        
        # 変更を適用
        for change in changes:
            await self._apply_change_to_virtual(virtual_env, change)
        
        # ビジュアルプレビュー生成
        visual_preview = await self.visual_renderer.render(virtual_env)
        
        # 差分計算
        diff = self.diff_calculator.calculate(current_state, virtual_env.state)
        
        # バージョン保存
        version_id = self.version_control.save({
            'timestamp': datetime.now(),
            'changes': changes,
            'state': virtual_env.state,
            'parent_version': context.get('parent_version')
        })
        
        return Preview(
            id=self._generate_preview_id(),
            version_id=version_id,
            visual=visual_preview,
            diff=diff,
            changes=changes,
            created_at=datetime.now(),
            revert_token=self._generate_revert_token(version_id),
            confidence_score=self._calculate_confidence(changes)
        )
    
    async def refine_preview(
        self, 
        current_preview: Preview, 
        refinement_request: str
    ) -> Preview:
        """
        プレビューの反復修正
        
        特徴:
        - 前回の変更を基に累積的に修正
        - 自然言語での修正指示に対応
        - 修正履歴を完全保持
        """
        
        # GPT-OSSで修正指示を解析
        refinement_analysis = await self.nlp_engine.analyze_refinement(
            refinement_request,
            current_preview.changes
        )
        
        # 修正を既存の変更にマージ
        adjusted_changes = self._merge_refinements(
            current_preview.changes,
            refinement_analysis.adjustments
        )
        
        # 新しいプレビューを生成
        new_preview = await self.generate_preview(
            adjusted_changes,
            {
                'service_id': current_preview.service_id,
                'parent_version': current_preview.version_id
            }
        )
        
        # 修正履歴を記録
        new_preview.refinement_history = [
            *current_preview.refinement_history,
            {
                'request': refinement_request,
                'timestamp': datetime.now(),
                'changes_applied': refinement_analysis.adjustments
            }
        ]
        
        return new_preview
    
    def _merge_refinements(
        self, 
        original_changes: List[Change], 
        adjustments: List[Adjustment]
    ) -> List[Change]:
        """
        修正を既存の変更にマージ
        
        例:
        元の変更: font-size: 16px → 20px
        修正指示: "もう少し小さく"
        結果: font-size: 16px → 18px
        """
        
        merged = original_changes.copy()
        
        for adjustment in adjustments:
            # 対象の変更を見つける
            target_index = self._find_target_change(merged, adjustment.target)
            
            if target_index >= 0:
                # 既存の変更を調整
                if adjustment.type == 'relative':
                    merged[target_index] = self._apply_relative_adjustment(
                        merged[target_index],
                        adjustment
                    )
                elif adjustment.type == 'replace':
                    merged[target_index] = adjustment.new_change
                elif adjustment.type == 'remove':
                    merged.pop(target_index)
            else:
                # 新しい変更として追加
                if adjustment.type == 'add':
                    merged.append(adjustment.new_change)
                    
        return merged
```

#### **2.2.2 バージョン管理システム**

```python
class PreviewVersionControl:
    """
    機能ID: F-PREVIEW-002
    プレビューのバージョン管理
    
    特徴:
    - 無制限のUndo/Redo
    - ブランチング対応
    - 差分表示
    - タイムトラベル機能
    """
    
    def __init__(self):
        self.versions = []  # 全バージョン履歴
        self.branches = {}  # ブランチ管理
        self.current_version = -1
        self.current_branch = 'main'
        
    def save_version(self, preview_data: Dict) -> str:
        """バージョン保存"""
        version = {
            'id': self._generate_version_id(),
            'timestamp': datetime.now(),
            'data': preview_data,
            'parent': self.versions[self.current_version]['id'] if self.current_version >= 0 else None,
            'branch': self.current_branch,
            'metadata': {
                'change_count': len(preview_data.get('changes', [])),
                'confidence': preview_data.get('confidence_score', 0),
                'user_feedback': None
            }
        }
        
        self.versions.append(version)
        self.current_version = len(self.versions) - 1
        
        return version['id']
    
    def undo(self) -> Optional[Dict]:
        """前のバージョンに戻る"""
        if self.current_version > 0:
            self.current_version -= 1
            return self.versions[self.current_version]
        return None
    
    def redo(self) -> Optional[Dict]:
        """次のバージョンに進む"""
        if self.current_version < len(self.versions) - 1:
            self.current_version += 1
            return self.versions[self.current_version]
        return None
    
    def create_branch(self, branch_name: str, from_version: Optional[str] = None) -> str:
        """ブランチ作成"""
        if from_version:
            branch_point = self._find_version(from_version)
        else:
            branch_point = self.current_version
            
        self.branches[branch_name] = {
            'created_at': datetime.now(),
            'branched_from': self.versions[branch_point]['id'],
            'versions': []
        }
        
        return branch_name
    
    def compare_versions(self, version1: str, version2: str) -> Dict:
        """バージョン間の差分"""
        v1 = self._find_version_data(version1)
        v2 = self._find_version_data(version2)
        
        return {
            'added': self._get_added_changes(v1, v2),
            'removed': self._get_removed_changes(v1, v2),
            'modified': self._get_modified_changes(v1, v2),
            'summary': self._generate_diff_summary(v1, v2)
        }
```

### **2.3 LPR (Login Protocol Receipt) システム**

#### **2.3.1 セキュア認証管理**

```typescript
interface LPRSystem {
  // 機能ID: F-AUTH-001
  // セキュリティレベル: Maximum
  // 準拠: OAuth 2.0, JWT, WebAuthn
  
  security_features: {
    encryption: 'ES256';              // ECDSA with P-256
    key_storage: 'TPM 2.0';          // ハードウェアセキュリティ
    ttl_hours: 2;                    // 短期有効期限
    device_binding: true;            // デバイスバインド
    scope_minimization: true;        // 最小権限
    audit_logging: true;             // 完全監査
  };
  
  // コア機能
  generateLPR(session: LoginSession, scopes: string[]): Promise<LPR>;
  validateLPR(lpr: string): Promise<ValidationResult>;
  revokeLPR(lpr: string): Promise<void>;
  auditOperation(lpr: string, operation: Operation): Promise<void>;
}
```

##### **実装詳細**

```python
# backend/src/services/auth/lpr_manager.py
import jwt
import hashlib
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from datetime import datetime, timedelta
import json

class LPRManager:
    """
    Login Protocol Receipt マネージャー
    
    セキュリティ機能:
    - ハードウェアキー管理（TPM 2.0）
    - デバイスバインディング
    - 最小権限スコープ
    - 短期TTL（2時間）
    - 完全監査証跡
    """
    
    def __init__(self, config: Dict):
        self.tpm = TPMInterface(config['tpm'])
        self.key_manager = SecureKeyManager(self.tpm)
        self.audit_logger = AuditLogger(config['audit'])
        self.scope_validator = ScopeValidator()
        
    async def generate_lpr(
        self,
        login_session: LoginSession,
        requested_scopes: List[str]
    ) -> LPR:
        """
        LPR生成
        
        セキュリティ要件:
        1. ユーザーの明示的同意
        2. 最小権限の原則
        3. デバイスバインディング
        4. 短期有効期限
        """
        
        # ログインセッション検証
        if not await self._verify_login_session(login_session):
            raise SecurityException("Invalid login session")
        
        # スコープ最小化
        minimal_scopes = self.scope_validator.minimize_scopes(
            requested_scopes,
            login_session.user_permissions
        )
        
        # デバイスフィンガープリント生成
        device_fingerprint = await self._generate_device_fingerprint()
        
        # LPRペイロード構築
        lpr_payload = {
            'lpr_version': '1.0',
            'subject_pseudonym': self._pseudonymize_user(login_session.user_id),
            'issued_at': datetime.utcnow().isoformat(),
            'expires_at': (datetime.utcnow() + timedelta(hours=2)).isoformat(),
            'origin_allowlist': login_session.allowed_origins,
            'scope_allowlist': minimal_scopes,
            'session_fingerprint': {
                'alg': 'SHA-256',
                'value': self._hash_session(login_session)
            },
            'device_fingerprint': device_fingerprint,
            'ua_public_key': await self.key_manager.get_public_key(),
            'policy': {
                'rate_limit_rps': 0.2,  # 5秒に1リクエスト
                'dom_action_limit': 200,
                'data_minimization': True,
                'require_mfa': login_session.mfa_verified
            },
            'audit_endpoint': 'mcp://audit/submit',
            'revocation_endpoint': 'mcp://login/revoke',
            'nonce': self._generate_nonce()
        }
        
        # TPMで署名
        signature = await self.tpm.sign(
            json.dumps(lpr_payload, sort_keys=True).encode(),
            self.key_manager.get_signing_key_handle()
        )
        
        # JWS形式で返却
        lpr_jws = self._create_jws(lpr_payload, signature)
        
        # 監査ログ
        await self.audit_logger.log({
            'event': 'lpr_generated',
            'user': lpr_payload['subject_pseudonym'],
            'scopes': minimal_scopes,
            'expires_at': lpr_payload['expires_at'],
            'device': device_fingerprint
        })
        
        return LPR(
            jws=lpr_jws,
            payload=lpr_payload,
            created_at=datetime.utcnow()
        )
    
    async def validate_scope(
        self,
        lpr: LPR,
        operation: Operation
    ) -> ValidationResult:
        """
        スコープ検証
        
        検証項目:
        1. URLパターンマッチング
        2. HTTPメソッド確認
        3. レート制限チェック
        4. データアクセス範囲
        """
        
        # 有効期限チェック
        if datetime.utcnow() > datetime.fromisoformat(lpr.payload['expires_at']):
            return ValidationResult(
                valid=False,
                reason='LPR expired',
                action='regenerate'
            )
        
        # デバイスバインディング確認
        current_device = await self._generate_device_fingerprint()
        if current_device != lpr.payload['device_fingerprint']:
            return ValidationResult(
                valid=False,
                reason='Device mismatch',
                action='block'
            )
        
        # スコープマッチング
        scope_match = False
        for scope in lpr.payload['scope_allowlist']:
            pattern = self._parse_scope_pattern(scope)
            if self._matches_pattern(operation, pattern):
                scope_match = True
                break
                
        if not scope_match:
            await self.audit_logger.log({
                'event': 'scope_violation',
                'lpr_id': lpr.payload['subject_pseudonym'],
                'attempted_operation': operation.to_dict(),
                'timestamp': datetime.utcnow()
            })
            
            return ValidationResult(
                valid=False,
                reason=f'Operation {operation} not in scope',
                action='deny'
            )
        
        # レート制限チェック
        if not await self._check_rate_limit(lpr, operation):
            return ValidationResult(
                valid=False,
                reason='Rate limit exceeded',
                action='throttle'
            )
        
        return ValidationResult(
            valid=True,
            reason='All checks passed'
        )
```

### **2.4 ブラウザ統合ダッシュボード**

#### **2.4.1 SaaS自動検出システム**

```typescript
interface SaaSDetectionSystem {
  // 機能ID: F-DASH-001
  // 検出可能サービス: 100+
  // リアルタイム更新: 5秒間隔
  
  detection_methods: {
    cookie_analysis: boolean;         // Cookie解析
    url_pattern_matching: boolean;    // URLパターン
    dom_inspection: boolean;          // DOM構造解析
    api_endpoint_detection: boolean;  // APIエンドポイント検出
    localStorage_scan: boolean;       // LocalStorage走査
  };
  
  // 検出パターンDB
  patterns: Map<string, ServicePattern>;
  
  // メソッド
  scanBrowser(): Promise<DetectedService[]>;
  monitorChanges(): Observable<ServiceChange>;
  getServiceCapabilities(service: string): Promise<Capability[]>;
}
```

##### **実装詳細**

```python
# backend/src/services/dashboard/saas_detector.py
import asyncio
from typing import List, Dict, Optional
import re
from datetime import datetime

class SaaSDetector:
    """
    SaaS自動検出システム
    100以上のサービスパターンを保持
    """
    
    def __init__(self):
        # サービスパターン定義（100+サービス）
        self.patterns = {
            'shopify': {
                'domains': [
                    r'\.myshopify\.com',
                    r'admin\.shopify\.com',
                    r'partners\.shopify\.com'
                ],
                'cookies': ['_shopify_s', '_shopify_y', '_s', '_shopify_fs'],
                'localStorage_keys': ['shopify_user', 'shopify_theme'],
                'api_endpoints': ['/admin/api/', '/graphql'],
                'dom_selectors': ['[data-shopify-editor]', '.shopify-section'],
                'capabilities': ['products', 'orders', 'customers', 'analytics'],
                'display_name': 'Shopify',
                'icon': '🛍️',
                'categories': ['EC', 'Commerce'],
                'priority': 1
            },
            'gmail': {
                'domains': [r'mail\.google\.com'],
                'cookies': ['GMAIL_AT', 'COMPASS', 'GMAIL_STAT'],
                'api_endpoints': ['/mail/u/'],
                'dom_selectors': ['[role="main"]', '[gh="tl"]'],
                'capabilities': ['email', 'labels', 'filters'],
                'display_name': 'Gmail',
                'icon': '📧',
                'categories': ['Email', 'Communication']
            },
            'stripe': {
                'domains': [r'dashboard\.stripe\.com'],
                'cookies': ['__stripe_sid', '__stripe_mid'],
                'api_endpoints': ['/v1/', '/graphql'],
                'capabilities': ['payments', 'subscriptions', 'invoices'],
                'display_name': 'Stripe',
                'icon': '💳',
                'categories': ['Payment', 'Finance']
            },
            # ... 100+ サービスパターン
        }
        
        self.browser_controller = BrowserController()
        self.cache = DetectionCache(ttl=300)  # 5分キャッシュ
        
    async def scan_browser(self) -> List[DetectedService]:
        """
        ブラウザ全体をスキャンしてSaaSを検出
        
        処理:
        1. 全タブを取得
        2. 各タブでパターンマッチング
        3. ログイン状態確認
        4. 機能検出
        5. 結果統合
        """
        
        detected_services = []
        
        # アクティブなブラウザコンテキストを取得
        contexts = await self.browser_controller.get_contexts()
        
        for context in contexts:
            pages = await context.pages()
            
            for page in pages:
                # キャッシュチェック
                page_url = page.url()
                cached = self.cache.get(page_url)
                if cached:
                    detected_services.append(cached)
                    continue
                
                # サービス検出
                service = await self._detect_service(page)
                if service:
                    # ログイン状態確認
                    service.is_logged_in = await self._check_login_status(page, service)
                    
                    # 利用可能機能の検出
                    if service.is_logged_in:
                        service.available_capabilities = await self._detect_capabilities(page, service)
                    
                    detected_services.append(service)
                    self.cache.set(page_url, service)
                    
        return self._deduplicate_services(detected_services)
    
    async def _detect_service(self, page) -> Optional[DetectedService]:
        """
        ページからサービスを検出
        
        検出方法の優先順位:
        1. URL パターンマッチング（最速）
        2. Cookie 分析
        3. LocalStorage 検査
        4. DOM 構造解析
        5. API エンドポイント検出
        """
        
        url = page.url()
        
        for service_key, pattern in self.patterns.items():
            # URL マッチング
            for domain_pattern in pattern.get('domains', []):
                if re.search(domain_pattern, url):
                    # 追加検証
                    confidence = 0.5  # URLマッチで50%
                    
                    # Cookie 検証
                    cookies = await page.context().cookies(url)
                    cookie_names = {c['name'] for c in cookies}
                    matching_cookies = len(
                        set(pattern.get('cookies', [])) & cookie_names
                    )
                    if matching_cookies > 0:
                        confidence += 0.2 * (matching_cookies / len(pattern.get('cookies', [])))
                    
                    # DOM 検証
                    for selector in pattern.get('dom_selectors', [])[:2]:  # 最初の2つだけチェック
                        try:
                            element = await page.query_selector(selector, timeout=1000)
                            if element:
                                confidence += 0.15
                        except:
                            pass
                            
                    if confidence >= 0.7:  # 70%以上の確信度で検出
                        return DetectedService(
                            service_key=service_key,
                            display_name=pattern['display_name'],
                            icon=pattern['icon'],
                            url=url,
                            confidence=confidence,
                            categories=pattern['categories'],
                            detected_at=datetime.utcnow(),
                            page_reference=page
                        )
                        
        return None
    
    async def _check_login_status(
        self,
        page,
        service: DetectedService
    ) -> bool:
        """
        ログイン状態の確認
        
        確認方法:
        1. セッションCookieの存在
        2. ログアウトボタンの存在
        3. ユーザー情報の表示
        4. APIレスポンス確認
        """
        
        pattern = self.patterns[service.service_key]
        
        # セッションCookie確認
        cookies = await page.context().cookies(service.url)
        session_cookies = [
            c for c in cookies
            if c['name'] in pattern.get('cookies', [])
            and c.get('expires', 0) > datetime.utcnow().timestamp()
        ]
        
        if session_cookies:
            # 追加のDOM確認
            try:
                # ログアウトボタンやユーザー名の存在確認
                user_indicators = [
                    '[data-user]',
                    '[aria-label*="account"]',
                    'button:has-text("ログアウト")',
                    'button:has-text("Sign out")',
                    'button:has-text("Log out")'
                ]
                
                for indicator in user_indicators:
                    element = await page.query_selector(indicator, timeout=1000)
                    if element:
                        return True
                        
            except:
                pass
                
        return False
```

### **2.5 Tool-Agnostic MCP統合**

#### **2.5.1 動的ツール統合システム**

```typescript
interface MCPIntegration {
  // 機能ID: F-MCP-001
  // 特徴: UI改修不要で新ツール追加可能
  
  capabilities: {
    auto_discovery: boolean;          // ツール自動発見
    dynamic_form_generation: boolean; // 動的フォーム生成
    schema_validation: boolean;       // スキーマ検証
    hot_reload: boolean;             // ホットリロード対応
    versioning: boolean;             // バージョン管理
  };
  
  // ツール管理
  registerTool(manifest: ToolManifest): Promise<void>;
  unregisterTool(toolId: string): Promise<void>;
  invokeTool(toolId: string, params: any): Promise<any>;
}
```

##### **実装詳細**

```python
# backend/src/services/mcp/mcp_server.py
import json
from typing import Dict, Any, List
import jsonschema
from jsonschema import validate

class MCPServer:
    """
    Model Context Protocol サーバー
    
    特徴:
    - ツールの動的登録・削除
    - JSON Schemaベースの検証
    - 統一インターフェース
    - ホットリロード対応
    """
    
    def __init__(self, config: Dict):
        self.tools = {}
        self.schema_validator = jsonschema.Draft7Validator
        self.execution_engine = ExecutionEngine(config['execution'])
        self.audit_logger = AuditLogger(config['audit'])
        
    async def register_tool(self, manifest: Dict) -> str:
        """
        新ツールの登録（UI改修不要）
        
        処理:
        1. マニフェスト検証
        2. スキーマ検証
        3. エンドポイント確認
        4. ツール登録
        5. UI通知
        """
        
        # マニフェスト検証
        self._validate_manifest(manifest)
        
        tool_id = manifest['id']
        
        # 既存ツールの上書き防止
        if tool_id in self.tools and not manifest.get('force', False):
            raise ValueError(f"Tool {tool_id} already exists")
        
        # ツールオブジェクト作成
        tool = MCPTool(
            id=tool_id,
            manifest=manifest,
            input_schema=manifest['input_schema'],
            output_schema=manifest['output_schema'],
            endpoint=manifest['endpoint'],
            scopes=manifest.get('scopes', []),
            policy=manifest.get('policy', {})
        )
        
        # エンドポイント到達確認
        if not await self._verify_endpoint(tool.endpoint):
            raise ConnectionError(f"Cannot reach endpoint: {tool.endpoint}")
        
        # 登録
        self.tools[tool_id] = tool
        
        # UIに通知（自動的にフォームが生成される）
        await self._notify_ui('tool_registered', {
            'tool_id': tool_id,
            'manifest': manifest
        })
        
        return tool_id
    
    async def invoke_tool(
        self,
        tool_id: str,
        params: Dict[str, Any],
        context: ExecutionContext
    ) -> Any:
        """
        ツール実行
        
        セキュリティ:
        1. 入力検証
        2. 権限確認
        3. レート制限
        4. 実行
        5. 出力検証
        6. 監査記録
        """
        
        tool = self.tools.get(tool_id)
        if not tool:
            raise ValueError(f"Tool not found: {tool_id}")
        
        # 入力検証
        try:
            validate(instance=params, schema=tool.input_schema)
        except jsonschema.exceptions.ValidationError as e:
            raise ValueError(f"Invalid input: {e.message}")
        
        # 権限確認
        if not await self._check_permissions(tool, context):
            raise PermissionError(f"Insufficient permissions for {tool_id}")
        
        # レート制限
        if not await self._check_rate_limit(tool, context):
            raise RateLimitError(f"Rate limit exceeded for {tool_id}")
        
        # 実行
        result = await self.execution_engine.execute(
            tool=tool,
            params=params,
            context=context
        )
        
        # 出力検証
        try:
            validate(instance=result, schema=tool.output_schema)
        except jsonschema.exceptions.ValidationError as e:
            raise ValueError(f"Invalid output from tool: {e.message}")
        
        # 監査記録
        await self.audit_logger.log({
            'tool_id': tool_id,
            'params': self._sanitize_params(params),
            'result_summary': self._summarize_result(result),
            'context': context.to_dict(),
            'timestamp': datetime.utcnow()
        })
        
        return result
    
    def _validate_manifest(self, manifest: Dict):
        """マニフェスト検証"""
        required_fields = [
            'id', 'version', 'input_schema', 
            'output_schema', 'endpoint'
        ]
        
        for field in required_fields:
            if field not in manifest:
                raise ValueError(f"Missing required field: {field}")
        
        # JSON Schema検証
        for schema_field in ['input_schema', 'output_schema']:
            try:
                self.schema_validator.check_schema(manifest[schema_field])
            except jsonschema.exceptions.SchemaError as e:
                raise ValueError(f"Invalid {schema_field}: {e.message}")
```

---

## **3. 技術アーキテクチャ**

### **3.1 GPT-OSS統合アーキテクチャ**

```yaml
AI処理層:
  推論エンジン:
    primary:
      model: GPT-OSS-20B
      quantization: INT4 (AWQ)
      vram_usage: 16GB
      throughput: 54 tokens/sec
      context_window: 128K
      
    secondary:
      model: Swallow-70B
      purpose: 日本語特化処理
      quantization: Q4_K_M
      vram_usage: 35GB
      
    lightweight:
      model: Phi-4
      purpose: 簡易タスク
      vram_usage: 8GB
      throughput: 100 tokens/sec
      
  推論サーバー:
    framework: vLLM
    features:
      - PagedAttention（メモリ効率24倍）
      - Continuous Batching（スループット5倍）
      - Prefix Caching（共通プロンプト高速化）
      - Speculative Decoding（推論高速化）
      
  最適化:
    - Flash Attention 2
    - KV Cache圧縮
    - Dynamic Batching
    - Model Parallelism（必要時）
```

### **3.2 システム全体構成**

```mermaid
graph TB
    subgraph "Client Layer"
        WEB[React SPA]
        MOBILE[PWA]
    end
    
    subgraph "API Gateway"
        GW[Kong / Nginx]
        AUTH[Auth Service]
    end
    
    subgraph "Application Layer"
        API[FastAPI]
        GQL[GraphQL]
        WS[WebSocket]
    end
    
    subgraph "AI Processing"
        VLLM[vLLM Server]
        GPT[GPT-OSS-20B]
        CACHE[Embedding Cache]
    end
    
    subgraph "Core Services"
        NLP[NLP Engine]
        PREVIEW[Preview Engine]
        LPR[LPR Manager]
        MCP[MCP Server]
    end
    
    subgraph "Execution"
        UA[User-Agent Farm]
        CDP[CDP Controllers]
    end
    
    subgraph "Data"
        PG[(PostgreSQL)]
        REDIS[(Redis)]
        S3[Object Storage]
    end
    
    WEB --> GW
    GW --> API
    API --> NLP
    NLP --> VLLM
    VLLM --> GPT
    API --> LPR
    API --> MCP
    MCP --> UA
```

---

## **4. 実装仕様**

### **4.1 プロジェクト構造**

```
shodo-ecosystem/
├── docker-compose.yml           # 開発環境定義
├── Makefile                     # ビルド・デプロイ自動化
│
├── frontend/                    # Reactアプリケーション
│   ├── src/
│   │   ├── features/           # 機能別モジュール
│   │   │   ├── nlp/           # 自然言語入力
│   │   │   ├── preview/       # プレビュー機能
│   │   │   ├── dashboard/     # ダッシュボード
│   │   │   └── auth/          # 認証
│   │   ├── components/         # 共通コンポーネント
│   │   ├── hooks/             # カスタムフック
│   │   ├── services/          # API通信
│   │   └── store/             # Redux Store
│   └── package.json
│
├── backend/                    # FastAPIサーバー
│   ├── src/
│   │   ├── api/               # APIエンドポイント
│   │   │   ├── v1/
│   │   │   └── graphql/
│   │   ├── services/          # ビジネスロジック
│   │   │   ├── nlp/          # NLP処理
│   │   │   ├── preview/      # プレビュー生成
│   │   │   ├── lpr/          # LPR管理
│   │   │   ├── mcp/          # MCPサーバー
│   │   │   └── dashboard/    # ダッシュボード
│   │   ├── models/            # データモデル
│   │   ├── workers/           # バックグラウンドジョブ
│   │   └── utils/             # ユーティリティ
│   ├── requirements.txt
│   └── Dockerfile
│
├── ai-server/                  # GPT-OSS推論サーバー
│   ├── src/
│   │   ├── vllm_server.py    # vLLMサーバー
│   │   ├── model_loader.py   # モデルローダー
│   │   └── optimizations/    # 最適化モジュール
│   ├── models/                # モデルファイル保存
│   └── Dockerfile
│
├── user-agent/                 # Playwright実装
│   ├── src/
│   │   ├── browser/          # ブラウザ制御
│   │   ├── detectors/        # SaaS検出
│   │   ├── executors/        # 操作実行
│   │   └── security/         # セキュリティ
│   └── Dockerfile
│
├── infrastructure/            # インフラ定義
│   ├── terraform/            # IaC
│   ├── kubernetes/           # K8s manifests
│   └── monitoring/           # Prometheus/Grafana
│
└── tests/                     # テスト
    ├── unit/
    ├── integration/
    └── e2e/
```

### **4.2 環境変数設定**

```bash
# .env.example

# AI設定
VLLM_MODEL=openai/gpt-oss-20b
VLLM_QUANTIZATION=awq
VLLM_GPU_MEMORY_UTILIZATION=0.95
VLLM_MAX_MODEL_LEN=128000
VLLM_TENSOR_PARALLEL_SIZE=1

# データベース
DATABASE_URL=postgresql://user:pass@localhost:5432/shodo
REDIS_URL=redis://localhost:6379

# セキュリティ
JWT_SECRET_KEY=your-secret-key-here
TPM_DEVICE_PATH=/dev/tpm0
ENCRYPTION_KEY=your-encryption-key

# サービス設定
API_PORT=8000
VLLM_PORT=8001
FRONTEND_PORT=3000

# 監査
AUDIT_LOG_PATH=/var/log/shodo/audit
AUDIT_RETENTION_DAYS=90

# レート制限
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_HOUR=1000
```

---

## **5. インフラ構成**

### **5.1 ハードウェア要件**

```yaml
開発環境:
  GPU: RTX 4090 (24GB)
  CPU: AMD Ryzen 9 7950X (16コア)
  RAM: 64GB DDR5
  SSD: 2TB NVMe Gen4
  月額コスト: 5万円
  
小規模本番（〜1,000 req/day）:
  GPU: RTX 4090 x1
  CPU: Intel Xeon E-2388G
  RAM: 128GB ECC
  SSD: 4TB NVMe RAID1
  月額コスト: 10万円
  
中規模本番（〜10,000 req/day）:
  GPU: RTX 4090 x2 or A100 40GB x1
  CPU: AMD EPYC 7543
  RAM: 256GB ECC
  SSD: 8TB NVMe RAID10
  月額コスト: 30万円
  
大規模本番（10,000+ req/day）:
  GPU: A100 80GB x2 or H100 x1
  CPU: Dual AMD EPYC 7763
  RAM: 512GB ECC
  SSD: 16TB NVMe RAID10
  月額コスト: 100万円
```

### **5.2 Docker Compose設定**

```yaml
# docker-compose.yml
version: '3.9'

services:
  # GPT-OSS推論サーバー
  vllm:
    build: ./ai-server
    runtime: nvidia
    ports:
      - "8001:8001"
    environment:
      - CUDA_VISIBLE_DEVICES=0
      - MODEL_NAME=openai/gpt-oss-20b
      - QUANTIZATION=awq
    volumes:
      - ./models:/models
      - ./cache:/cache
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    
  # バックエンドAPI
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - VLLM_URL=http://vllm:8001
    depends_on:
      - postgres
      - redis
      - vllm
    
  # フロントエンド
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - REACT_APP_API_URL=http://localhost:8000
    
  # User-Agent
  user-agent:
    build: ./user-agent
    environment:
      - PLAYWRIGHT_BROWSERS_PATH=/browsers
    volumes:
      - ./browser-data:/data
    
  # データベース
  postgres:
    image: postgres:15
    environment:
      - POSTGRES_DB=shodo
      - POSTGRES_USER=shodo
      - POSTGRES_PASSWORD=secure_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    
  # キャッシュ
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

---

## **6. 開発手順書**

### **6.1 開発環境セットアップ（1日目）**

```bash
# 1. リポジトリクローン
git clone https://github.com/your-org/shodo-ecosystem.git
cd shodo-ecosystem

# 2. GPT-OSSモデルダウンロード
python scripts/download_models.py --model gpt-oss-20b --quantization awq

# 3. 環境変数設定
cp .env.example .env
# .envを編集

# 4. Docker環境起動
docker-compose up -d

# 5. データベース初期化
docker-compose exec backend python -m alembic upgrade head
docker-compose exec backend python scripts/seed_data.py

# 6. 動作確認
curl http://localhost:8000/health
curl http://localhost:8001/v1/models
```

### **6.2 段階的実装計画**

#### **Week 1: 基盤構築**

```bash
# Day 1-2: 環境構築とGPT-OSS導入
- [ ] 開発環境セットアップ
- [ ] GPT-OSSモデル設定
- [ ] vLLMサーバー起動確認
- [ ] 基本的な推論テスト

# Day 3-4: NLP基礎実装
- [ ] 二重経路解析エンジン
- [ ] ルールベース処理
- [ ] AI統合
- [ ] 基本的な意図解析

# Day 5-7: API基盤
- [ ] FastAPI設定
- [ ] GraphQL スキーマ定義
- [ ] 基本エンドポイント実装
- [ ] 認証基盤
```

#### **Week 2: コア機能実装**

```bash
# Day 8-10: プレビュー機能
- [ ] サンドボックス環境構築
- [ ] プレビュー生成エンジン
- [ ] 差分計算
- [ ] バージョン管理

# Day 11-14: LPRシステム
- [ ] 認証フロー実装
- [ ] LPR生成・検証
- [ ] スコープ管理
- [ ] セキュリティ実装
```

#### **Week 3: 統合機能**

```bash
# Day 15-17: ダッシュボード
- [ ] SaaS検出システム
- [ ] リアルタイム更新
- [ ] 統合UI実装

# Day 18-21: MCP統合
- [ ] ツール登録システム
- [ ] 動的フォーム生成
- [ ] 実行エンジン
```

#### **Week 4: 完成・最適化**

```bash
# Day 22-24: 最適化
- [ ] パフォーマンスチューニング
- [ ] キャッシュ戦略
- [ ] エラーハンドリング

# Day 25-28: テスト・デプロイ
- [ ] 統合テスト
- [ ] 負荷テスト
- [ ] セキュリティ監査
- [ ] 本番デプロイ
```

---

## **7. テスト仕様**

### **7.1 テスト戦略**

```yaml
テストピラミッド:
  単体テスト: 70%
    - 各モジュールの機能テスト
    - エッジケース検証
    - モック使用
    
  統合テスト: 20%
    - サービス間連携
    - データベース統合
    - API動作確認
    
  E2Eテスト: 10%
    - 主要シナリオ20本
    - UI操作フロー
    - 実環境相当
    
カバレッジ目標:
  - コード: 80%以上
  - ブランチ: 70%以上
  - 主要パス: 100%
```

### **7.2 テストケース例**

```python
# tests/unit/test_nlp_engine.py
import pytest
from services.nlp import DualPathEngine

class TestNLPEngine:
    @pytest.fixture
    def engine(self):
        return DualPathEngine(test_config)
    
    async def test_japanese_analysis(self, engine):
        """日本語解析テスト"""
        result = await engine.analyze("Shopifyの注文をエクスポートして")
        
        assert result.intent == "export"
        assert result.service == "shopify"
        assert result.target == "orders"
        assert result.confidence > 0.8
    
    async def test_ambiguity_resolution(self, engine):
        """曖昧性解決テスト"""
        result = await engine.analyze("もっと大きく")
        
        assert result.requires_confirmation == True
        assert len(result.suggestions) >= 3
        assert result.confidence < 0.7
    
    async def test_refinement(self, engine):
        """修正処理テスト"""
        initial = await engine.analyze("価格を変更")
        refined = await engine.refine(initial, "1000円に")
        
        assert refined.entities['price'] == 1000
        assert refined.entities['currency'] == 'JPY'
```

---

## **8. 運用仕様**

### **8.1 監視項目**

```yaml
インフラメトリクス:
  - GPU使用率: < 80%
  - GPUメモリ: < 22GB
  - CPU使用率: < 70%
  - メモリ使用率: < 80%
  - ディスクI/O: < 1000 IOPS

アプリケーションメトリクス:
  - レスポンスタイム: p95 < 500ms
  - スループット: > 100 req/min
  - エラーレート: < 1%
  - LPR生成成功率: > 99%

ビジネスメトリクス:
  - 日次アクティブユーザー
  - 処理リクエスト数
  - サービス別利用率
  - エラー発生頻度
```

### **8.2 運用手順**

```bash
# 日次運用
- ログ確認
- メトリクス確認
- アラート対応

# 週次運用  
- パフォーマンスレビュー
- セキュリティパッチ適用
- バックアップ確認

# 月次運用
- キャパシティプランニング
- コスト最適化
- セキュリティ監査
```

---

## **まとめ**

本仕様書は、**GPT-OSS-20B**を活用した**shodo ecosystem**の完全な実装ガイドです。

### **実現される価値**

1. **コスト削減**: 月額200万円 → 5万円（97.5%削減）
2. **性能向上**: 15倍の高速化
3. **セキュリティ**: 完全ローカル処理
4. **拡張性**: UI改修不要で新機能追加

### **次のステップ**

1. 開発環境構築（1日）
2. MVP実装（1週間）
3. 本番展開（1ヶ月）

**月額5万円で、エンタープライズグレードのAI統合システムが実現可能です。**
