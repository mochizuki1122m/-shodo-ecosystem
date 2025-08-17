import { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  TextField,
  Grid,
  Card,
  CardContent,
  Chip,
  IconButton,
  Divider,
  List,
  ListItem,
  ListItemText,
  Alert,
} from '@mui/material';
import {
  Preview as PreviewIcon,
  Edit as EditIcon,
  Undo as UndoIcon,
  Redo as RedoIcon,
  Save as SaveIcon,
  Refresh as RefreshIcon,
  Compare as CompareIcon,
} from '@mui/icons-material';
import { motion } from 'framer-motion';

interface PreviewData {
  id: string;
  version: number;
  html: string;
  css: string;
  changes: Array<{
    type: string;
    target: string;
    property: string;
    oldValue: any;
    newValue: any;
  }>;
  confidence: number;
}

const PreviewEditor: React.FC = () => {
  const [currentPreview, setCurrentPreview] = useState<PreviewData | null>(null);
  const [refinementInput, setRefinementInput] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [history, setHistory] = useState<PreviewData[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);

  // モックプレビューデータ
  const generateMockPreview = (): PreviewData => ({
    id: `preview_${Date.now()}`,
    version: history.length + 1,
    html: `
      <div class="preview-container">
        <h1 class="title">サンプルタイトル</h1>
        <p class="description">これはプレビューの説明文です</p>
        <div class="price">¥1,000</div>
        <button class="action-button">購入する</button>
      </div>
    `,
    css: `
      .preview-container {
        padding: 20px;
        font-family: sans-serif;
      }
      .title {
        font-size: 24px;
        color: #333;
        margin-bottom: 10px;
      }
      .description {
        font-size: 14px;
        color: #666;
        margin-bottom: 15px;
      }
      .price {
        font-size: 20px;
        font-weight: bold;
        color: #e74c3c;
        margin-bottom: 20px;
      }
      .action-button {
        background: #3498db;
        color: white;
        border: none;
        padding: 10px 20px;
        border-radius: 4px;
        cursor: pointer;
      }
    `,
    changes: [
      {
        type: 'style',
        target: '.title',
        property: 'font-size',
        oldValue: '16px',
        newValue: '24px',
      },
      {
        type: 'content',
        target: '.price',
        property: 'text',
        oldValue: '¥2,000',
        newValue: '¥1,000',
      },
    ],
    confidence: 0.85,
  });

  const handleGeneratePreview = () => {
    const newPreview = generateMockPreview();
    setCurrentPreview(newPreview);
    setHistory([...history.slice(0, historyIndex + 1), newPreview]);
    setHistoryIndex(historyIndex + 1);
  };

  const handleRefine = () => {
    if (!currentPreview || !refinementInput) return;

    // 簡単な修正シミュレーション
    const refinedPreview = { ...currentPreview };
    
    // 価格の変更を検出
    const priceMatch = refinementInput.match(/(\d+)円/);
    if (priceMatch) {
      refinedPreview.html = refinedPreview.html.replace(
        /<div class="price">.*?<\/div>/,
        `<div class="price">¥${priceMatch[1]}</div>`
      );
      refinedPreview.changes.push({
        type: 'content',
        target: '.price',
        property: 'text',
        oldValue: currentPreview.html.match(/<div class="price">(.*?)<\/div>/)?.[1],
        newValue: `¥${priceMatch[1]}`,
      });
    }

    // サイズ変更を検出
    if (refinementInput.includes('大きく')) {
      refinedPreview.css = refinedPreview.css.replace(
        /font-size: 24px/,
        'font-size: 32px'
      );
      refinedPreview.changes.push({
        type: 'style',
        target: '.title',
        property: 'font-size',
        oldValue: '24px',
        newValue: '32px',
      });
    }

    refinedPreview.version = history.length + 1;
    refinedPreview.id = `preview_${Date.now()}`;

    setCurrentPreview(refinedPreview);
    setHistory([...history.slice(0, historyIndex + 1), refinedPreview]);
    setHistoryIndex(historyIndex + 1);
    setRefinementInput('');
  };

  const handleUndo = () => {
    if (historyIndex > 0) {
      setHistoryIndex(historyIndex - 1);
      setCurrentPreview(history[historyIndex - 1]);
    }
  };

  const handleRedo = () => {
    if (historyIndex < history.length - 1) {
      setHistoryIndex(historyIndex + 1);
      setCurrentPreview(history[historyIndex + 1]);
    }
  };

  const handleApply = () => {
    // 本番環境への適用（実際はAPIコール）
    alert('プレビューを本番環境に適用しました');
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        プレビュー編集
      </Typography>

      {/* ツールバー */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          <Button
            variant="contained"
            startIcon={<PreviewIcon />}
            onClick={handleGeneratePreview}
          >
            プレビュー生成
          </Button>
          
          <IconButton
            onClick={handleUndo}
            disabled={historyIndex <= 0}
            title="元に戻す"
          >
            <UndoIcon />
          </IconButton>
          
          <IconButton
            onClick={handleRedo}
            disabled={historyIndex >= history.length - 1}
            title="やり直す"
          >
            <RedoIcon />
          </IconButton>
          
          <Box sx={{ flexGrow: 1 }} />
          
          {currentPreview && (
            <>
              <Chip
                label={`v${currentPreview.version}`}
                color="primary"
                size="small"
              />
              <Chip
                label={`確信度: ${(currentPreview.confidence * 100).toFixed(0)}%`}
                color={currentPreview.confidence > 0.7 ? 'success' : 'warning'}
                size="small"
              />
              <Button
                variant="outlined"
                startIcon={<SaveIcon />}
                onClick={handleApply}
                color="success"
              >
                本番適用
              </Button>
            </>
          )}
        </Box>
      </Paper>

      {currentPreview ? (
        <Grid container spacing={3}>
          {/* プレビュー表示 */}
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  プレビュー
                </Typography>
                <Paper
                  sx={{
                    p: 2,
                    bgcolor: 'background.default',
                    minHeight: 400,
                    position: 'relative',
                  }}
                >
                  <style dangerouslySetInnerHTML={{ __html: currentPreview.css }} />
                  <div dangerouslySetInnerHTML={{ __html: currentPreview.html }} />
                </Paper>
              </CardContent>
            </Card>
          </Grid>

          {/* 変更履歴と修正入力 */}
          <Grid item xs={12} md={6}>
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  修正入力
                </Typography>
                <TextField
                  fullWidth
                  multiline
                  rows={3}
                  variant="outlined"
                  placeholder="修正内容を日本語で入力（例：価格を500円にして、タイトルをもっと大きく）"
                  value={refinementInput}
                  onChange={(e) => setRefinementInput(e.target.value)}
                  sx={{ mb: 2 }}
                />
                <Button
                  variant="contained"
                  startIcon={<RefreshIcon />}
                  onClick={handleRefine}
                  disabled={!refinementInput}
                  fullWidth
                >
                  修正を適用
                </Button>
              </CardContent>
            </Card>

            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  変更履歴
                </Typography>
                <List dense>
                  {currentPreview.changes.map((change, index) => (
                    <ListItem key={index}>
                      <ListItemText
                        primary={`${change.target} の ${change.property}`}
                        secondary={`${change.oldValue} → ${change.newValue}`}
                      />
                    </ListItem>
                  ))}
                </List>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      ) : (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <PreviewIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
          <Typography variant="h6" color="text.secondary">
            プレビューを生成してください
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            「プレビュー生成」ボタンをクリックして開始
          </Typography>
        </Paper>
      )}

      {/* 機能説明 */}
      <Alert severity="info" sx={{ mt: 3 }}>
        <Typography variant="subtitle2" gutterBottom>
          無限修正プレビュー機能
        </Typography>
        <Typography variant="body2">
          • 本番環境に影響なく、何度でも修正可能
        </Typography>
        <Typography variant="body2">
          • 日本語で修正指示を入力するだけ
        </Typography>
        <Typography variant="body2">
          • 全バージョンの履歴を保持、いつでもロールバック可能
        </Typography>
      </Alert>
    </Box>
  );
};

export default PreviewEditor;