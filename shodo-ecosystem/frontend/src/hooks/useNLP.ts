import { useMutation, useQuery, useQueryClient, useInfiniteQuery } from '@tanstack/react-query';
import nlpService, {
  NLPRequest,
  NLPResponse,
  NLPSession,
  RuleDefinition,
  NLPBatchRequest,
  NLPBatchResponse
} from '../services/api/nlp.service';

// クエリキー
const QUERY_KEYS = {
  sessions: ['nlp', 'sessions'],
  session: (id: string) => ['nlp', 'sessions', id],
  rules: ['nlp', 'rules'],
  rule: (id: string) => ['nlp', 'rules', id],
  categories: ['nlp', 'categories'],
  statistics: ['nlp', 'statistics'],
  analysisHistory: (sessionId: string) => ['nlp', 'sessions', sessionId, 'history'],
};

/**
 * テキスト解析フック
 */
export function useAnalyzeText() {
  const queryClient = useQueryClient();

  return useMutation<NLPResponse, Error, NLPRequest>({
    mutationFn: (request) => nlpService.analyzeText(request),
    onSuccess: (data) => {
      // セッション一覧を再取得
      if (data.session_id) {
        queryClient.invalidateQueries({ queryKey: QUERY_KEYS.sessions });
        queryClient.invalidateQueries({ 
          queryKey: QUERY_KEYS.analysisHistory(data.session_id) 
        });
      }
    },
  });
}

/**
 * バッチ解析フック
 */
export function useAnalyzeBatch() {
  return useMutation<NLPBatchResponse, Error, NLPBatchRequest>({
    mutationFn: (request) => nlpService.analyzeBatch(request),
  });
}

/**
 * セッション一覧取得フック（無限スクロール対応）
 */
export function useNLPSessions() {
  return useInfiniteQuery({
    queryKey: QUERY_KEYS.sessions,
    queryFn: ({ pageParam = 1 }) => 
      nlpService.getSessions({
        page: pageParam,
        per_page: 20,
        sort_by: 'created_at',
        sort_order: 'desc',
      }),
    getNextPageParam: (lastPage) => 
      lastPage.has_next ? lastPage.page + 1 : undefined,
    staleTime: 5 * 60 * 1000, // 5分
  });
}

/**
 * セッション詳細取得フック
 */
export function useNLPSession(sessionId: string) {
  return useQuery<NLPSession, Error>({
    queryKey: QUERY_KEYS.session(sessionId),
    queryFn: () => nlpService.getSession(sessionId),
    enabled: !!sessionId,
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * セッション削除フック
 */
export function useDeleteNLPSession() {
  const queryClient = useQueryClient();

  return useMutation<void, Error, string>({
    mutationFn: (sessionId) => nlpService.deleteSession(sessionId),
    onSuccess: (_, sessionId) => {
      // キャッシュから削除
      queryClient.removeQueries({ queryKey: QUERY_KEYS.session(sessionId) });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.sessions });
    },
  });
}

/**
 * ルール一覧取得フック
 */
export function useNLPRules(params?: {
  category?: string;
  is_active?: boolean;
}) {
  return useQuery<RuleDefinition[], Error>({
    queryKey: [...QUERY_KEYS.rules, params],
    queryFn: () => nlpService.getRules(params),
    staleTime: 10 * 60 * 1000, // 10分
  });
}

/**
 * ルール作成フック
 */
export function useCreateRule() {
  const queryClient = useQueryClient();

  return useMutation<RuleDefinition, Error, Omit<RuleDefinition, 'rule_id' | 'created_at' | 'updated_at'>>({
    mutationFn: (rule) => nlpService.createRule(rule),
    onSuccess: (data) => {
      // ルール一覧を再取得
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.rules });
      // 新しいルールをキャッシュに追加
      queryClient.setQueryData(QUERY_KEYS.rule(data.rule_id), data);
    },
  });
}

/**
 * ルール更新フック
 */
export function useUpdateRule() {
  const queryClient = useQueryClient();

  return useMutation<RuleDefinition, Error, { ruleId: string; updates: Partial<RuleDefinition> }>({
    mutationFn: ({ ruleId, updates }) => nlpService.updateRule(ruleId, updates),
    onSuccess: (data) => {
      // ルール詳細を更新
      queryClient.setQueryData(QUERY_KEYS.rule(data.rule_id), data);
      // ルール一覧を再取得
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.rules });
    },
  });
}

/**
 * ルール削除フック
 */
export function useDeleteRule() {
  const queryClient = useQueryClient();

  return useMutation<void, Error, string>({
    mutationFn: (ruleId) => nlpService.deleteRule(ruleId),
    onSuccess: (_, ruleId) => {
      // キャッシュから削除
      queryClient.removeQueries({ queryKey: QUERY_KEYS.rule(ruleId) });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.rules });
    },
  });
}

/**
 * 解析履歴取得フック（無限スクロール対応）
 */
export function useAnalysisHistory(sessionId: string) {
  return useInfiniteQuery({
    queryKey: QUERY_KEYS.analysisHistory(sessionId),
    queryFn: ({ pageParam = 1 }) => 
      nlpService.getAnalysisHistory(sessionId, {
        page: pageParam,
        per_page: 10,
      }),
    getNextPageParam: (lastPage) => 
      lastPage.has_next ? lastPage.page + 1 : undefined,
    enabled: !!sessionId,
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * カテゴリ一覧取得フック
 */
export function useNLPCategories() {
  return useQuery<string[], Error>({
    queryKey: QUERY_KEYS.categories,
    queryFn: () => nlpService.getCategories(),
    staleTime: 30 * 60 * 1000, // 30分
  });
}

/**
 * 統計情報取得フック
 */
export function useNLPStatistics(params?: {
  start_date?: string;
  end_date?: string;
}) {
  return useQuery({
    queryKey: [...QUERY_KEYS.statistics, params],
    queryFn: () => nlpService.getStatistics(params),
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * 解析結果エクスポートフック
 */
export function useExportAnalysis() {
  return useMutation<Blob, Error, { analysisId: string; format: 'json' | 'csv' | 'pdf' }>({
    mutationFn: ({ analysisId, format }) => nlpService.exportAnalysis(analysisId, format),
    onSuccess: (blob, { analysisId, format }) => {
      // ダウンロード処理
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `analysis_${analysisId}.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    },
  });
}

/**
 * ストリーミング解析フック
 */
export function useStreamAnalysis() {
  return useMutation<AsyncGenerator<Partial<NLPResponse>>, Error, NLPRequest>({
    mutationFn: (request) => nlpService.streamAnalysis(request),
  });
}