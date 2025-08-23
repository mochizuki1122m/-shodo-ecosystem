"""
サンドボックスプレビューエンジン
本番環境に影響なく無限に修正可能なプレビューシステム
"""

import hashlib
import uuid
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import logging
import copy

logger = logging.getLogger(__name__)

@dataclass
class Change:
    """変更内容"""
    type: str  # 'style', 'content', 'structure', 'data'
    target: str  # 変更対象のセレクタやID
    property: str  # 変更するプロパティ
    old_value: Any  # 変更前の値
    new_value: Any  # 変更後の値
    metadata: Dict = None

@dataclass
class Preview:
    """プレビューオブジェクト"""
    id: str
    version_id: str
    service: str
    visual: Dict  # ビジュアルプレビューデータ (html, css, javascript)
    diff: Dict  # 差分情報
    changes: List[Change]
    created_at: datetime
    revert_token: str
    confidence: float  # Renamed from confidence_score for API consistency
    refinement_history: List[Dict] = None

class VirtualEnvironment:
    """仮想環境"""
    def __init__(self, state: Dict):
        self.state = copy.deepcopy(state)
        self.id = str(uuid.uuid4())
    
    def apply_change(self, change: Change):
        """変更を適用"""
        # 実際の変更処理（簡略化）
        if change.type == "style":
            if "styles" not in self.state:
                self.state["styles"] = {}
            self.state["styles"][change.target] = {
                change.property: change.new_value
            }
        elif change.type == "content":
            if "content" not in self.state:
                self.state["content"] = {}
            self.state["content"][change.target] = change.new_value
        elif change.type == "data":
            if "data" not in self.state:
                self.state["data"] = {}
            self.state["data"][change.property] = change.new_value

class VersionControl:
    """バージョン管理システム"""
    def __init__(self):
        self.versions = []
        self.branches = {}
        self.current_version = -1
        self.current_branch = "main"
    
    def save(self, data: Dict) -> str:
        """バージョン保存"""
        version_id = str(uuid.uuid4())
        version = {
            "id": version_id,
            "timestamp": datetime.now().isoformat(),
            "data": data,
            "branch": self.current_branch,
            "parent": self.versions[self.current_version]["id"] if self.current_version >= 0 else None
        }
        self.versions.append(version)
        self.current_version = len(self.versions) - 1
        return version_id
    
    def get_version(self, version_id: str) -> Optional[Dict]:
        """特定バージョンの取得"""
        for version in self.versions:
            if version["id"] == version_id:
                return version
        return None
    
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

class DiffCalculator:
    """差分計算"""
    def calculate(self, old_state: Dict, new_state: Dict) -> Dict:
        """状態間の差分を計算"""
        diff = {
            "added": {},
            "removed": {},
            "modified": {},
            "summary": ""
        }
        
        # 追加された要素
        for key in new_state:
            if key not in old_state:
                diff["added"][key] = new_state[key]
        
        # 削除された要素
        for key in old_state:
            if key not in new_state:
                diff["removed"][key] = old_state[key]
        
        # 変更された要素
        for key in old_state:
            if key in new_state and old_state[key] != new_state[key]:
                diff["modified"][key] = {
                    "old": old_state[key],
                    "new": new_state[key]
                }
        
        # サマリー生成
        diff["summary"] = f"追加: {len(diff['added'])}項目, 削除: {len(diff['removed'])}項目, 変更: {len(diff['modified'])}項目"
        
        return diff

class VisualRenderer:
    """ビジュアルレンダリング"""
    async def render(self, virtual_env: VirtualEnvironment) -> Dict:
        """仮想環境をビジュアル化"""
        # 実際のレンダリング処理（簡略化）
        return {
            "html": self._generate_html(virtual_env.state),
            "css": self._generate_css(virtual_env.state.get("styles", {})),
            "screenshot": None,  # スクリーンショットURL
            "interactive": True
        }
    
    def _generate_html(self, state: Dict) -> str:
        """HTML生成"""
        content = state.get("content", {})
        html_parts = ["<div class='preview-container'>"]
        
        for key, value in content.items():
            html_parts.append(f"<div id='{key}'>{value}</div>")
        
        html_parts.append("</div>")
        return "\n".join(html_parts)
    
    def _generate_css(self, styles: Dict) -> str:
        """CSS生成"""
        css_parts = []
        
        for selector, properties in styles.items():
            css_parts.append(f"{selector} {{")
            for prop, value in properties.items():
                css_parts.append(f"  {prop}: {value};")
            css_parts.append("}")
        
        return "\n".join(css_parts)

class SandboxPreviewEngine:
    """サンドボックスプレビューエンジン"""
    
    def __init__(self, max_versions: int = 100, cache_size: int = 50):
        """Initialize with dependency injection
        
        Args:
            max_versions: Maximum number of versions to keep
            cache_size: Maximum number of virtual environments to cache
        """
        self.max_versions = max_versions
        self.cache_size = cache_size
        self.version_control = VersionControl()
        self.diff_calculator = DiffCalculator()
        self.visual_renderer = VisualRenderer()
        self.virtual_environments = {}  # 仮想環境のキャッシュ
    
    async def generate_preview(
        self,
        changes: List[Change],
        context: Dict
    ) -> Preview:
        """
        プレビュー生成
        
        Args:
            changes: 適用する変更リスト
            context: コンテキスト情報（サービスID、現在の状態など）
            
        Returns:
            Preview: 生成されたプレビュー
        """
        
        # 現在の状態を取得（実際はデータベースやAPIから取得）
        current_state = await self._get_current_state(context["service_id"])
        
        # 仮想環境を作成
        virtual_env = VirtualEnvironment(current_state)
        
        # 変更を適用
        for change in changes:
            virtual_env.apply_change(change)
        
        # ビジュアルプレビュー生成
        visual_preview = await self.visual_renderer.render(virtual_env)
        
        # 差分計算
        diff = self.diff_calculator.calculate(current_state, virtual_env.state)
        
        # バージョン保存
        version_id = self.version_control.save({
            "changes": [asdict(c) for c in changes],
            "state": virtual_env.state,
            "parent_version": context.get("parent_version")
        })
        
        # プレビューオブジェクト生成
        preview = Preview(
            id=self._generate_preview_id(),
            version_id=version_id,
            service=context["service_id"],
            visual=visual_preview,
            diff=diff,
            changes=changes,
            created_at=datetime.now(),
            revert_token=self._generate_revert_token(version_id),
            confidence=self._calculate_confidence(changes),
            refinement_history=[]
        )
        
        # 仮想環境をキャッシュ
        self.virtual_environments[preview.id] = virtual_env
        
        return preview
    
    async def refine_preview(
        self,
        current_preview: Preview,
        refinement_request: str
    ) -> Preview:
        """
        プレビューの反復修正
        
        Args:
            current_preview: 現在のプレビュー
            refinement_request: 修正指示（自然言語）
            
        Returns:
            Preview: 修正されたプレビュー
        """
        
        # 修正指示を解析（NLPエンジンを使用）
        refinement_analysis = await self._analyze_refinement(
            refinement_request,
            current_preview.changes
        )
        
        # 修正を既存の変更にマージ
        adjusted_changes = self._merge_refinements(
            current_preview.changes,
            refinement_analysis["adjustments"]
        )
        
        # 新しいプレビューを生成
        new_preview = await self.generate_preview(
            adjusted_changes,
            {
                "service_id": current_preview.service,
                "parent_version": current_preview.version_id
            }
        )
        
        # 修正履歴を記録
        new_preview.refinement_history = [
            *(current_preview.refinement_history or []),
            {
                "request": refinement_request,
                "timestamp": datetime.now().isoformat(),
                "changes_applied": refinement_analysis["adjustments"]
            }
        ]
        
        return new_preview
    
    async def apply_to_production(self, preview: Preview) -> Dict:
        """
        プレビューを本番環境に適用
        
        Args:
            preview: 適用するプレビュー
            
        Returns:
            Dict: 適用結果
        """
        
        # 実際の適用処理（APIコールなど）
        result = {
            "status": "success",
            "applied_changes": len(preview.changes),
            "timestamp": datetime.now().isoformat(),
            "rollback_token": self._generate_rollback_token(preview.version_id)
        }
        
        # 適用履歴を保存
        self._save_application_history(preview, result)
        
        return result
    
    async def rollback(self, version_id: str) -> Dict:
        """
        指定バージョンへのロールバック
        
        Args:
            version_id: ロールバック先のバージョンID
            
        Returns:
            Dict: ロールバック結果
        """
        
        version = self.version_control.get_version(version_id)
        if not version:
            raise ValueError(f"Version not found: {version_id}")
        
        # ロールバック処理
        result = {
            "status": "success",
            "rolled_back_to": version_id,
            "timestamp": datetime.now().isoformat()
        }
        
        return result
    
    def _merge_refinements(
        self,
        original_changes: List[Change],
        adjustments: List[Dict]
    ) -> List[Change]:
        """修正を既存の変更にマージ"""
        
        merged = original_changes.copy()
        
        for adjustment in adjustments:
            if adjustment["type"] == "modify":
                # 既存の変更を修正
                for i, change in enumerate(merged):
                    if change.target == adjustment["target"] and \
                       change.property == adjustment["property"]:
                        merged[i].new_value = adjustment["new_value"]
                        break
            elif adjustment["type"] == "add":
                # 新しい変更を追加
                merged.append(Change(
                    type=adjustment["change_type"],
                    target=adjustment["target"],
                    property=adjustment["property"],
                    old_value=adjustment.get("old_value"),
                    new_value=adjustment["new_value"]
                ))
            elif adjustment["type"] == "remove":
                # 変更を削除
                merged = [c for c in merged if not (
                    c.target == adjustment["target"] and
                    c.property == adjustment["property"]
                )]
        
        return merged
    
    async def _analyze_refinement(
        self,
        refinement_request: str,
        current_changes: List[Change]
    ) -> Dict:
        """修正指示を解析"""
        
        # 簡略化された解析（実際はNLPエンジンを使用）
        adjustments = []
        
        # 相対的な修正の検出
        if "もっと" in refinement_request:
            if "大きく" in refinement_request:
                adjustments.append({
                    "type": "modify",
                    "target": current_changes[-1].target if current_changes else "default",
                    "property": "font-size",
                    "new_value": "24px"
                })
            elif "小さく" in refinement_request:
                adjustments.append({
                    "type": "modify",
                    "target": current_changes[-1].target if current_changes else "default",
                    "property": "font-size",
                    "new_value": "12px"
                })
        
        # 具体的な値の検出
        import re
        price_match = re.search(r"(\d+)円", refinement_request)
        if price_match:
            adjustments.append({
                "type": "modify",
                "target": "price",
                "property": "value",
                "new_value": int(price_match.group(1))
            })
        
        return {"adjustments": adjustments}
    
    async def _get_current_state(self, service_id: str) -> Dict:
        """現在の状態を取得"""
        # 実際はデータベースやAPIから取得
        return {
            "service": service_id,
            "content": {
                "title": "サンプルタイトル",
                "description": "サンプル説明文",
                "price": "1000円"
            },
            "styles": {
                ".title": {
                    "font-size": "16px",
                    "color": "#333"
                }
            }
        }
    
    def _generate_preview_id(self) -> str:
        """プレビューID生成"""
        return f"preview_{uuid.uuid4().hex[:8]}"
    
    def _generate_revert_token(self, version_id: str) -> str:
        """リバートトークン生成"""
        return hashlib.sha256(f"{version_id}:{datetime.now()}".encode()).hexdigest()[:16]
    
    def _generate_rollback_token(self, version_id: str) -> str:
        """ロールバックトークン生成"""
        return hashlib.sha256(f"rollback:{version_id}".encode()).hexdigest()[:16]
    
    def _calculate_confidence(self, changes: List[Change]) -> float:
        """変更の確信度を計算"""
        if not changes:
            return 0.0
        
        # 簡略化された確信度計算
        base_confidence = 0.8
        
        # 変更数による調整
        if len(changes) > 5:
            base_confidence *= 0.9
        
        return min(base_confidence, 1.0)
    
    def _save_application_history(self, preview: Preview, result: Dict):
        """適用履歴を保存"""
        # 実際はデータベースに保存
        logger.info(f"Applied preview {preview.id}: {result}")