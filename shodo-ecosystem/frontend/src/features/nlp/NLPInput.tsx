import { useState, useRef, useEffect } from 'react';
import {
  Box,
  Paper,
  TextField,
  Button,
  Typography,
  Chip,
  Alert,
  CircularProgress,
  Card,
  CardContent,
  IconButton,
  Tooltip,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
} from '@mui/material';
import {
  Send as SendIcon,
  Clear as ClearIcon,
  Psychology as PsychologyIcon,
  Speed as SpeedIcon,
  CheckCircle as CheckCircleIcon,
  Help as HelpIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { motion, AnimatePresence } from 'framer-motion';
import { useMutation } from '@tanstack/react-query';
import { analyzeText } from '../../services/api';

interface AnalysisResult {
  intent: string;
  confidence: number;
  entities: Record<string, any>;
  service?: string;
  requires_confirmation: boolean;
  suggestions: string[];
  processing_path: string;
  processing_time_ms: number;
}

const NLPInput: React.FC = () => {
  const [input, setInput] = useState('');
  const [history, setHistory] = useState<Array<{ input: string; result: AnalysisResult }>>([]);
  const [selectedSuggestion, setSelectedSuggestion] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const analyzeMutation = useMutation({
    mutationFn: (text: string) => analyzeText(text),
    onSuccess: (data, variables) => {
      setHistory(prev => [...prev, { input: variables, result: data }]);
      setInput('');
      if (data.requires_confirmation && data.suggestions.length > 0) {
        setSelectedSuggestion(null);
      }
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim()) {
      analyzeMutation.mutate(input);
    }
  };

  const handleSuggestionClick = (suggestion: string) => {
    setSelectedSuggestion(suggestion);
    setInput(suggestion);
    inputRef.current?.focus();
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'success';
    if (confidence >= 0.6) return 'warning';
    return 'error';
  };

  const getProcessingPathIcon = (path: string) => {
    switch (path) {
      case 'rule':
      case 'rule_primary':
        return <SpeedIcon />;
      case 'ai':
      case 'ai_primary':
        return <PsychologyIcon />;
      default:
        return <CheckCircleIcon />;
    }
  };

  return (
    <Box sx={{ maxWidth: 1200, mx: 'auto', p: 3 }}>
      <Typography variant="h4" gutterBottom sx={{ mb: 4 }}>
        自然言語インターフェース
      </Typography>

      {/* 入力フォーム */}
      <Paper elevation={3} sx={{ p: 3, mb: 4 }}>
        <form onSubmit={handleSubmit}>
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-start' }}>
            <TextField
              ref={inputRef}
              fullWidth
              multiline
              minRows={2}
              maxRows={4}
              variant="outlined"
              placeholder="日本語で操作を入力してください（例：Shopifyの今月の売上を確認して）"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={analyzeMutation.isPending}
              sx={{ flex: 1 }}
            />
            <Button
              type="submit"
              variant="contained"
              size="large"
              disabled={!input.trim() || analyzeMutation.isPending}
              startIcon={analyzeMutation.isPending ? <CircularProgress size={20} /> : <SendIcon />}
              sx={{ height: 56 }}
            >
              解析
            </Button>
            <IconButton
              onClick={() => setInput('')}
              disabled={!input || analyzeMutation.isPending}
              sx={{ height: 56 }}
            >
              <ClearIcon />
            </IconButton>
          </Box>
        </form>

        {/* サンプル入力 */}
        <Box sx={{ mt: 2 }}>
          <Typography variant="caption" color="text.secondary">
            サンプル入力:
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 1 }}>
            {[
              'Shopifyの商品を一覧表示',
              'Gmailで未読メールを確認',
              'Stripeの今月の売上を見る',
              '価格を1000円に変更して',
            ].map((sample) => (
              <Chip
                key={sample}
                label={sample}
                size="small"
                onClick={() => setInput(sample)}
                clickable
                variant="outlined"
              />
            ))}
          </Box>
        </Box>
      </Paper>

      {/* エラー表示 */}
      {analyzeMutation.isError && (
        <Alert severity="error" sx={{ mb: 3 }}>
          解析中にエラーが発生しました。もう一度お試しください。
        </Alert>
      )}

      {/* 解析結果履歴 */}
      <AnimatePresence>
        {history.map((item, index) => (
          <motion.div
            key={index}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.3 }}
          >
            <Card sx={{ mb: 3 }}>
              <CardContent>
                {/* 入力内容 */}
                <Box sx={{ mb: 2 }}>
                  <Typography variant="subtitle2" color="text.secondary">
                    入力:
                  </Typography>
                  <Typography variant="body1">{item.input}</Typography>
                </Box>

                <Divider sx={{ my: 2 }} />

                {/* 解析結果 */}
                <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
                  {/* 意図 */}
                  <Box>
                    <Typography variant="subtitle2" color="text.secondary">
                      検出された意図:
                    </Typography>
                    <Typography variant="h6">{item.result.intent}</Typography>
                  </Box>

                  {/* 確信度 */}
                  <Box>
                    <Typography variant="subtitle2" color="text.secondary">
                      確信度:
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Chip
                        label={`${(item.result.confidence * 100).toFixed(1)}%`}
                        color={getConfidenceColor(item.result.confidence)}
                        size="small"
                      />
                    </Box>
                  </Box>

                  {/* サービス */}
                  {item.result.service && (
                    <Box>
                      <Typography variant="subtitle2" color="text.secondary">
                        対象サービス:
                      </Typography>
                      <Chip label={item.result.service} color="primary" size="small" />
                    </Box>
                  )}

                  {/* 処理経路 */}
                  <Box>
                    <Typography variant="subtitle2" color="text.secondary">
                      処理経路:
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      {getProcessingPathIcon(item.result.processing_path)}
                      <Typography variant="body2">
                        {item.result.processing_path}
                      </Typography>
                    </Box>
                  </Box>

                  {/* 処理時間 */}
                  <Box>
                    <Typography variant="subtitle2" color="text.secondary">
                      処理時間:
                    </Typography>
                    <Typography variant="body2">
                      {item.result.processing_time_ms.toFixed(1)}ms
                    </Typography>
                  </Box>
                </Box>

                {/* エンティティ */}
                {Object.keys(item.result.entities).length > 0 && (
                  <Box sx={{ mt: 2 }}>
                    <Typography variant="subtitle2" color="text.secondary">
                      抽出されたエンティティ:
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 1 }}>
                      {Object.entries(item.result.entities).map(([key, value]) => (
                        <Chip
                          key={key}
                          label={`${key}: ${JSON.stringify(value)}`}
                          size="small"
                          variant="outlined"
                        />
                      ))}
                    </Box>
                  </Box>
                )}

                {/* 確認が必要な場合の提案 */}
                {item.result.requires_confirmation && item.result.suggestions.length > 0 && (
                  <Box sx={{ mt: 3 }}>
                    <Alert severity="info" icon={<HelpIcon />}>
                      <Typography variant="subtitle2" sx={{ mb: 1 }}>
                        より正確な処理のため、以下の情報を追加してください:
                      </Typography>
                      <List dense>
                        {item.result.suggestions.map((suggestion, idx) => (
                          <ListItem
                            key={idx}
                            button
                            onClick={() => handleSuggestionClick(suggestion)}
                            sx={{
                              bgcolor: selectedSuggestion === suggestion ? 'action.selected' : 'transparent',
                              borderRadius: 1,
                              mb: 0.5,
                            }}
                          >
                            <ListItemIcon>
                              <RefreshIcon fontSize="small" />
                            </ListItemIcon>
                            <ListItemText primary={suggestion} />
                          </ListItem>
                        ))}
                      </List>
                    </Alert>
                  </Box>
                )}
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </AnimatePresence>

      {/* 履歴が空の場合 */}
      {history.length === 0 && !analyzeMutation.isPending && (
        <Paper sx={{ p: 4, textAlign: 'center', bgcolor: 'background.default' }}>
          <PsychologyIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
          <Typography variant="h6" color="text.secondary">
            自然な日本語で操作を入力してください
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            AIが意図を理解し、適切なサービスと操作を特定します
          </Typography>
        </Paper>
      )}
    </Box>
  );
};

export default NLPInput;