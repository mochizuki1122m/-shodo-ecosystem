import apiClient, { ApiResponse, PaginatedResponse } from '../apiClient';

// 型定義
export interface PreviewRequest {
  source_type: string;
  source_id: string;
  target_element?: string;
  modifications: Record<string, any>;
  preview_type?: 'html' | 'css' | 'json' | 'markdown' | 'component';
  context?: Record<string, any>;
  session_id?: string;
}

export interface Change {
  change_id: string;
  type: 'content' | 'style' | 'structure' | 'attribute' | 'script';
  target: string;
  property: string;
  old_value: any;
  new_value: any;
  description?: string;
  impact_level: 'low' | 'medium' | 'high' | 'critical';
}

export interface PreviewData {
  preview_id: string;
  version: number;
  html?: string;
  css?: string;
  javascript?: string;
  changes: Change[];
  confidence: number;
  metadata: Record<string, any>;
  created_at: string;
}

export interface PreviewResponse {
  session_id: string;
  preview_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  preview_data: PreviewData;
  preview_url?: string;
  expires_at: string;
  can_apply: boolean;
  warnings: string[];
}

export interface RefinementRequest {
  preview_id: string;
  refinement_text: string;
  keep_history?: boolean;
}

export interface ApplyRequest {
  preview_id: string;
  target_environment?: string;
  dry_run?: boolean;
  backup?: boolean;
  approval_token?: string;
}

export interface ApplyResponse {
  apply_id: string;
  status: 'pending' | 'approved' | 'rejected' | 'applied' | 'rolled_back';
  applied_changes: Change[];
  rollback_id?: string;
  backup_id?: string;
  timestamp: string;
}

export interface RollbackRequest {
  apply_id: string;
  rollback_to?: string;
  reason: string;
}

export interface RollbackResponse {
  rollback_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  rolled_back_changes: Change[];
  timestamp: string;
}

export interface PreviewHistory {
  history_id: string;
  preview_id: string;
  version: number;
  changes: Change[];
  created_by: string;
  created_at: string;
  parent_version?: number;
}

export interface PreviewSession {
  session_id: string;
  user_id: string;
  created_at: string;
  updated_at: string;
  preview_count: number;
  apply_count: number;
  rollback_count: number;
  metadata: Record<string, any>;
}

class PreviewService {
  /**
   * プレビュー生成
   */
  async generatePreview(request: PreviewRequest): Promise<PreviewResponse> {
    const response = await apiClient.post<PreviewResponse>('/preview/generate', request);
    
    if (response.success && response.data) {
      return response.data;
    }
    
    throw new Error(response.error || 'Preview generation failed');
  }

  /**
   * プレビュー修正
   */
  async refinePreview(request: RefinementRequest): Promise<PreviewResponse> {
    const response = await apiClient.post<PreviewResponse>('/preview/refine', request);
    
    if (response.success && response.data) {
      return response.data;
    }
    
    throw new Error(response.error || 'Preview refinement failed');
  }

  /**
   * プレビュー適用
   */
  async applyPreview(request: ApplyRequest): Promise<ApplyResponse> {
    const response = await apiClient.post<ApplyResponse>('/preview/apply', request);
    
    if (response.success && response.data) {
      return response.data;
    }
    
    throw new Error(response.error || 'Preview application failed');
  }

  /**
   * ロールバック
   */
  async rollback(request: RollbackRequest): Promise<RollbackResponse> {
    const response = await apiClient.post<RollbackResponse>('/preview/rollback', request);
    
    if (response.success && response.data) {
      return response.data;
    }
    
    throw new Error(response.error || 'Rollback failed');
  }

  /**
   * プレビュー取得
   */
  async getPreview(previewId: string): Promise<PreviewResponse> {
    const response = await apiClient.get<PreviewResponse>(`/preview/${previewId}`);
    
    if (response.success && response.data) {
      return response.data;
    }
    
    throw new Error(response.error || 'Failed to get preview');
  }

  /**
   * プレビューHTML取得
   */
  async getPreviewHtml(previewId: string): Promise<string> {
    const response = await apiClient.get(`/preview/view/${previewId}`, {
      responseType: 'text'
    });
    
    return response.data as unknown as string;
  }

  /**
   * プレビュー履歴取得
   */
  async getPreviewHistory(previewId: string): Promise<PreviewHistory[]> {
    const response = await apiClient.get<PreviewHistory[]>(`/preview/history/${previewId}`);
    
    if (response.success && response.data) {
      return response.data;
    }
    
    throw new Error(response.error || 'Failed to get preview history');
  }

  /**
   * プレビューセッション一覧取得
   */
  async getSessions(params?: {
    page?: number;
    per_page?: number;
    sort_by?: string;
    sort_order?: 'asc' | 'desc';
  }): Promise<PaginatedResponse<PreviewSession>> {
    const response = await apiClient.get<PaginatedResponse<PreviewSession>>('/preview/sessions', {
      params
    });
    
    if (response.success && response.data) {
      return response.data;
    }
    
    throw new Error(response.error || 'Failed to get sessions');
  }

  /**
   * プレビューセッション詳細取得
   */
  async getSession(sessionId: string): Promise<PreviewSession> {
    const response = await apiClient.get<PreviewSession>(`/preview/sessions/${sessionId}`);
    
    if (response.success && response.data) {
      return response.data;
    }
    
    throw new Error(response.error || 'Failed to get session');
  }

  /**
   * プレビュー削除
   */
  async deletePreview(previewId: string): Promise<void> {
    const response = await apiClient.delete(`/preview/${previewId}`);
    
    if (!response.success) {
      throw new Error(response.error || 'Failed to delete preview');
    }
  }

  /**
   * 承認リクエスト
   */
  async requestApproval(previewId: string, approvers: string[]): Promise<{
    approval_id: string;
    status: string;
    expires_at: string;
  }> {
    const response = await apiClient.post(`/preview/${previewId}/request-approval`, {
      approvers
    });
    
    if (response.success && response.data) {
      return response.data;
    }
    
    throw new Error(response.error || 'Failed to request approval');
  }

  /**
   * 承認
   */
  async approve(previewId: string, approvalId: string): Promise<void> {
    const response = await apiClient.post(`/preview/${previewId}/approve`, {
      approval_id: approvalId
    });
    
    if (!response.success) {
      throw new Error(response.error || 'Failed to approve');
    }
  }

  /**
   * 却下
   */
  async reject(previewId: string, approvalId: string, reason: string): Promise<void> {
    const response = await apiClient.post(`/preview/${previewId}/reject`, {
      approval_id: approvalId,
      reason
    });
    
    if (!response.success) {
      throw new Error(response.error || 'Failed to reject');
    }
  }

  /**
   * 差分比較
   */
  async compareVersions(previewId: string, version1: number, version2: number): Promise<{
    additions: Change[];
    deletions: Change[];
    modifications: Change[];
  }> {
    const response = await apiClient.get(`/preview/${previewId}/compare`, {
      params: { v1: version1, v2: version2 }
    });
    
    if (response.success && response.data) {
      return response.data;
    }
    
    throw new Error(response.error || 'Failed to compare versions');
  }

  /**
   * プレビューのクローン
   */
  async clonePreview(previewId: string, name?: string): Promise<PreviewResponse> {
    const response = await apiClient.post<PreviewResponse>(`/preview/${previewId}/clone`, {
      name
    });
    
    if (response.success && response.data) {
      return response.data;
    }
    
    throw new Error(response.error || 'Failed to clone preview');
  }

  /**
   * バックアップ一覧取得
   */
  async getBackups(previewId: string): Promise<Array<{
    backup_id: string;
    created_at: string;
    size: number;
    description?: string;
  }>> {
    const response = await apiClient.get(`/preview/${previewId}/backups`);
    
    if (response.success && response.data) {
      return response.data;
    }
    
    throw new Error(response.error || 'Failed to get backups');
  }

  /**
   * バックアップから復元
   */
  async restoreFromBackup(previewId: string, backupId: string): Promise<PreviewResponse> {
    const response = await apiClient.post<PreviewResponse>(`/preview/${previewId}/restore`, {
      backup_id: backupId
    });
    
    if (response.success && response.data) {
      return response.data;
    }
    
    throw new Error(response.error || 'Failed to restore from backup');
  }
}

const previewService = new PreviewService();
export default previewService;