import apiClient, { ApiResponse, PaginatedResponse } from '../apiClient';

// 型定義
export interface NLPRequest {
  text: string;
  text_type?: 'plain' | 'html' | 'markdown' | 'json';
  analysis_type?: 'rule_based' | 'ai_based' | 'hybrid';
  options?: Record<string, any>;
  context?: Record<string, any>;
  session_id?: string;
}

export interface RuleMatch {
  rule_id: string;
  rule_name: string;
  category: string;
  matched_text: string;
  position: {
    start: number;
    end: number;
  };
  confidence: number;
  metadata: Record<string, any>;
}

export interface AIAnalysis {
  intent: string;
  entities: Array<Record<string, any>>;
  sentiment: Record<string, number>;
  keywords: string[];
  summary?: string;
  confidence: number;
  model_version: string;
}

export interface NLPResponse {
  session_id: string;
  analysis_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  rule_matches: RuleMatch[];
  ai_analysis?: AIAnalysis;
  combined_score: number;
  processing_time_ms: number;
  timestamp: string;
}

export interface NLPSession {
  session_id: string;
  user_id: string;
  created_at: string;
  updated_at: string;
  analysis_count: number;
  total_tokens: number;
  metadata: Record<string, any>;
}

export interface RuleDefinition {
  rule_id: string;
  name: string;
  category: string;
  pattern: string;
  description: string;
  priority: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface NLPBatchRequest {
  items: NLPRequest[];
  parallel?: boolean;
  priority?: number;
}

export interface NLPBatchResponse {
  batch_id: string;
  total: number;
  completed: number;
  failed: number;
  results: NLPResponse[];
  processing_time_ms: number;
  timestamp: string;
}

class NLPService {
  /**
   * テキスト解析
   */
  async analyzeText(request: NLPRequest): Promise<NLPResponse> {
    const response = await apiClient.post<NLPResponse>('/nlp/analyze', request);
    
    if (response.success && response.data) {
      return response.data;
    }
    
    throw new Error(response.error || 'Analysis failed');
  }

  /**
   * バッチテキスト解析
   */
  async analyzeBatch(request: NLPBatchRequest): Promise<NLPBatchResponse> {
    const response = await apiClient.post<NLPBatchResponse>('/nlp/analyze/batch', request);
    
    if (response.success && response.data) {
      return response.data;
    }
    
    throw new Error(response.error || 'Batch analysis failed');
  }

  /**
   * セッション一覧取得
   */
  async getSessions(params?: {
    page?: number;
    per_page?: number;
    sort_by?: string;
    sort_order?: 'asc' | 'desc';
  }): Promise<PaginatedResponse<NLPSession>> {
    const response = await apiClient.get<PaginatedResponse<NLPSession>>('/nlp/sessions', {
      params
    });
    
    if (response.success && response.data) {
      return response.data;
    }
    
    throw new Error(response.error || 'Failed to get sessions');
  }

  /**
   * セッション詳細取得
   */
  async getSession(sessionId: string): Promise<NLPSession> {
    const response = await apiClient.get<NLPSession>(`/nlp/sessions/${sessionId}`);
    
    if (response.success && response.data) {
      return response.data;
    }
    
    throw new Error(response.error || 'Failed to get session');
  }

  /**
   * セッション削除
   */
  async deleteSession(sessionId: string): Promise<void> {
    const response = await apiClient.delete(`/nlp/sessions/${sessionId}`);
    
    if (!response.success) {
      throw new Error(response.error || 'Failed to delete session');
    }
  }

  /**
   * ルール一覧取得
   */
  async getRules(params?: {
    category?: string;
    is_active?: boolean;
  }): Promise<RuleDefinition[]> {
    const response = await apiClient.get<RuleDefinition[]>('/nlp/rules', {
      params
    });
    
    if (response.success && response.data) {
      return response.data;
    }
    
    throw new Error(response.error || 'Failed to get rules');
  }

  /**
   * ルール作成
   */
  async createRule(rule: Omit<RuleDefinition, 'rule_id' | 'created_at' | 'updated_at'>): Promise<RuleDefinition> {
    const response = await apiClient.post<RuleDefinition>('/nlp/rules', rule);
    
    if (response.success && response.data) {
      return response.data;
    }
    
    throw new Error(response.error || 'Failed to create rule');
  }

  /**
   * ルール更新
   */
  async updateRule(ruleId: string, updates: Partial<RuleDefinition>): Promise<RuleDefinition> {
    const response = await apiClient.patch<RuleDefinition>(`/nlp/rules/${ruleId}`, updates);
    
    if (response.success && response.data) {
      return response.data;
    }
    
    throw new Error(response.error || 'Failed to update rule');
  }

  /**
   * ルール削除
   */
  async deleteRule(ruleId: string): Promise<void> {
    const response = await apiClient.delete(`/nlp/rules/${ruleId}`);
    
    if (!response.success) {
      throw new Error(response.error || 'Failed to delete rule');
    }
  }

  /**
   * ストリーミング解析
   */
  async *streamAnalysis(request: NLPRequest): AsyncGenerator<Partial<NLPResponse>> {
    const cancelToken = apiClient.createCancelToken();
    
    try {
      for await (const chunk of apiClient.stream<Partial<NLPResponse>>('/nlp/analyze/stream', {
        method: 'POST',
        data: request,
        cancelToken: cancelToken.token
      })) {
        yield chunk;
      }
    } catch (error) {
      if (!apiClient.isCancel(error)) {
        throw error;
      }
    }
  }

  /**
   * 解析履歴取得
   */
  async getAnalysisHistory(sessionId: string, params?: {
    page?: number;
    per_page?: number;
  }): Promise<PaginatedResponse<NLPResponse>> {
    const response = await apiClient.get<PaginatedResponse<NLPResponse>>(
      `/nlp/sessions/${sessionId}/history`,
      { params }
    );
    
    if (response.success && response.data) {
      return response.data;
    }
    
    throw new Error(response.error || 'Failed to get analysis history');
  }

  /**
   * 解析結果のエクスポート
   */
  async exportAnalysis(analysisId: string, format: 'json' | 'csv' | 'pdf' = 'json'): Promise<Blob> {
    const response = await apiClient.get(`/nlp/analysis/${analysisId}/export`, {
      params: { format },
      responseType: 'blob'
    });
    
    return response.data as unknown as Blob;
  }

  /**
   * カテゴリ一覧取得
   */
  async getCategories(): Promise<string[]> {
    const response = await apiClient.get<string[]>('/nlp/categories');
    
    if (response.success && response.data) {
      return response.data;
    }
    
    throw new Error(response.error || 'Failed to get categories');
  }

  /**
   * 統計情報取得
   */
  async getStatistics(params?: {
    start_date?: string;
    end_date?: string;
  }): Promise<{
    total_analyses: number;
    total_tokens: number;
    average_confidence: number;
    top_intents: Array<{ intent: string; count: number }>;
    daily_usage: Array<{ date: string; count: number }>;
  }> {
    const response = await apiClient.get('/nlp/statistics', { params });
    
    if (response.success && response.data) {
      return response.data;
    }
    
    throw new Error(response.error || 'Failed to get statistics');
  }
}

const nlpService = new NLPService();
export default nlpService;