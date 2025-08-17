import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Alert,
  CircularProgress,
  Tooltip,
  Grid,
  Switch,
  FormControlLabel,
  Tabs,
  Tab,
  Badge,
  LinearProgress,
} from '@mui/material';
import {
  Add as AddIcon,
  Refresh as RefreshIcon,
  Delete as DeleteIcon,
  Key as KeyIcon,
  Visibility as VisibilityIcon,
  VisibilityOff as VisibilityOffIcon,
  ContentCopy as CopyIcon,
  RotateLeft as RotateIcon,
  Timeline as TimelineIcon,
  Security as SecurityIcon,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
} from '@mui/icons-material';
import { useAppDispatch, useAppSelector } from '../../store';
import { apiService } from '../../services/api';
import { format } from 'date-fns';
import { ja } from 'date-fns/locale';

interface APIKey {
  id: string;
  key_id: string;
  service: string;
  name: string;
  status: 'active' | 'expired' | 'revoked' | 'pending';
  created_at: string;
  expires_at?: string;
  permissions: string[];
  auto_renew: boolean;
  last_used_at?: string;
  usage_count?: number;
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div hidden={value !== index} {...other}>
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );
}

export const APIKeyManagement: React.FC = () => {
  const dispatch = useAppDispatch();
  const [apiKeys, setApiKeys] = useState<APIKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [openDialog, setOpenDialog] = useState(false);
  const [selectedKey, setSelectedKey] = useState<APIKey | null>(null);
  const [showKey, setShowKey] = useState<{ [key: string]: boolean }>({});
  const [tabValue, setTabValue] = useState(0);
  const [statistics, setStatistics] = useState<any>(null);

  // 新規APIキー作成用の状態
  const [newKey, setNewKey] = useState({
    service: '',
    name: '',
    auto_renew: true,
    credentials: {} as Record<string, string>,
  });

  // サービスリスト
  const services = [
    { value: 'shopify', label: 'Shopify', icon: '🛍️' },
    { value: 'stripe', label: 'Stripe', icon: '💳' },
    { value: 'github', label: 'GitHub', icon: '🐙' },
    { value: 'gmail', label: 'Gmail', icon: '📧' },
    { value: 'slack', label: 'Slack', icon: '💬' },
  ];

  useEffect(() => {
    fetchAPIKeys();
    fetchStatistics();
  }, []);

  const fetchAPIKeys = async () => {
    try {
      setLoading(true);
      const response = await apiService.get('/api/keys');
      setApiKeys(response.data);
    } catch (error) {
      console.error('Failed to fetch API keys:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchStatistics = async () => {
    try {
      const response = await apiService.get('/api/keys/statistics/summary');
      setStatistics(response.data);
    } catch (error) {
      console.error('Failed to fetch statistics:', error);
    }
  };

  const handleCreateKey = async () => {
    try {
      const response = await apiService.post('/api/keys/acquire', newKey);
      setApiKeys([...apiKeys, response.data]);
      setOpenDialog(false);
      setNewKey({
        service: '',
        name: '',
        auto_renew: true,
        credentials: {},
      });
    } catch (error) {
      console.error('Failed to create API key:', error);
    }
  };

  const handleRefreshKey = async (keyId: string) => {
    try {
      await apiService.post(`/api/keys/${keyId}/refresh`);
      fetchAPIKeys();
    } catch (error) {
      console.error('Failed to refresh API key:', error);
    }
  };

  const handleRevokeKey = async (keyId: string) => {
    if (!window.confirm('このAPIキーを無効化してもよろしいですか？')) {
      return;
    }
    try {
      await apiService.delete(`/api/keys/${keyId}`, {
        data: { reason: 'User requested revocation' },
      });
      fetchAPIKeys();
    } catch (error) {
      console.error('Failed to revoke API key:', error);
    }
  };

  const handleRotateKey = async (keyId: string) => {
    try {
      const response = await apiService.post(`/api/keys/${keyId}/rotate`);
      alert(`キーのローテーションを開始しました。タスクID: ${response.data.task_id}`);
      fetchAPIKeys();
    } catch (error) {
      console.error('Failed to rotate API key:', error);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    // TODO: Show success notification
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'success';
      case 'expired':
        return 'warning';
      case 'revoked':
        return 'error';
      case 'pending':
        return 'info';
      default:
        return 'default';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'active':
        return <CheckCircleIcon fontSize="small" />;
      case 'expired':
        return <WarningIcon fontSize="small" />;
      case 'revoked':
        return <ErrorIcon fontSize="small" />;
      default:
        return null;
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
        <Typography variant="h4" component="h1">
          APIキー管理
        </Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => setOpenDialog(true)}
        >
          新規APIキー
        </Button>
      </Box>

      {/* 統計カード */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="textSecondary" gutterBottom>
                アクティブキー
              </Typography>
              <Typography variant="h4">
                {apiKeys.filter((k) => k.status === 'active').length}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="textSecondary" gutterBottom>
                総リクエスト数
              </Typography>
              <Typography variant="h4">
                {statistics?.total_requests || 0}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="textSecondary" gutterBottom>
                成功率
              </Typography>
              <Typography variant="h4">
                {statistics?.success_rate || 0}%
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="textSecondary" gutterBottom>
                期限切れ間近
              </Typography>
              <Typography variant="h4" color="warning.main">
                {apiKeys.filter((k) => {
                  if (!k.expires_at) return false;
                  const daysUntilExpiry =
                    (new Date(k.expires_at).getTime() - Date.now()) /
                    (1000 * 60 * 60 * 24);
                  return daysUntilExpiry < 7 && daysUntilExpiry > 0;
                }).length}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* タブ */}
      <Paper sx={{ mb: 3 }}>
        <Tabs value={tabValue} onChange={(e, v) => setTabValue(v)}>
          <Tab
            label={
              <Badge badgeContent={apiKeys.length} color="primary">
                すべてのキー
              </Badge>
            }
          />
          <Tab
            label={
              <Badge
                badgeContent={apiKeys.filter((k) => k.status === 'active').length}
                color="success"
              >
                アクティブ
              </Badge>
            }
          />
          <Tab
            label={
              <Badge
                badgeContent={
                  apiKeys.filter((k) => k.status === 'expired' || k.status === 'revoked')
                    .length
                }
                color="error"
              >
                無効
              </Badge>
            }
          />
        </Tabs>
      </Paper>

      {/* APIキーテーブル */}
      <TableContainer component={Paper}>
        {loading ? (
          <LinearProgress />
        ) : (
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>サービス</TableCell>
                <TableCell>名前</TableCell>
                <TableCell>キーID</TableCell>
                <TableCell>ステータス</TableCell>
                <TableCell>作成日</TableCell>
                <TableCell>有効期限</TableCell>
                <TableCell>自動更新</TableCell>
                <TableCell align="right">アクション</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {apiKeys
                .filter((key) => {
                  if (tabValue === 0) return true;
                  if (tabValue === 1) return key.status === 'active';
                  if (tabValue === 2)
                    return key.status === 'expired' || key.status === 'revoked';
                  return true;
                })
                .map((key) => (
                  <TableRow key={key.id}>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <span>
                          {services.find((s) => s.value === key.service)?.icon}
                        </span>
                        <Typography>
                          {services.find((s) => s.value === key.service)?.label}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>{key.name}</TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Typography
                          sx={{
                            fontFamily: 'monospace',
                            fontSize: '0.875rem',
                          }}
                        >
                          {showKey[key.id]
                            ? key.key_id
                            : `${key.key_id.substring(0, 8)}...`}
                        </Typography>
                        <IconButton
                          size="small"
                          onClick={() =>
                            setShowKey({ ...showKey, [key.id]: !showKey[key.id] })
                          }
                        >
                          {showKey[key.id] ? (
                            <VisibilityOffIcon fontSize="small" />
                          ) : (
                            <VisibilityIcon fontSize="small" />
                          )}
                        </IconButton>
                        <IconButton
                          size="small"
                          onClick={() => copyToClipboard(key.key_id)}
                        >
                          <CopyIcon fontSize="small" />
                        </IconButton>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={key.status}
                        color={getStatusColor(key.status) as any}
                        size="small"
                        icon={getStatusIcon(key.status) as any}
                      />
                    </TableCell>
                    <TableCell>
                      {format(new Date(key.created_at), 'yyyy/MM/dd', { locale: ja })}
                    </TableCell>
                    <TableCell>
                      {key.expires_at ? (
                        <Box>
                          {format(new Date(key.expires_at), 'yyyy/MM/dd', {
                            locale: ja,
                          })}
                          {new Date(key.expires_at) < new Date() && (
                            <Chip
                              label="期限切れ"
                              color="error"
                              size="small"
                              sx={{ ml: 1 }}
                            />
                          )}
                        </Box>
                      ) : (
                        '無期限'
                      )}
                    </TableCell>
                    <TableCell>
                      <Switch checked={key.auto_renew} disabled size="small" />
                    </TableCell>
                    <TableCell align="right">
                      <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
                        <Tooltip title="更新">
                          <IconButton
                            size="small"
                            onClick={() => handleRefreshKey(key.key_id)}
                            disabled={key.status !== 'active'}
                          >
                            <RefreshIcon />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="ローテーション">
                          <IconButton
                            size="small"
                            onClick={() => handleRotateKey(key.key_id)}
                            disabled={key.status !== 'active'}
                          >
                            <RotateIcon />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="統計">
                          <IconButton
                            size="small"
                            onClick={() => setSelectedKey(key)}
                          >
                            <TimelineIcon />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="無効化">
                          <IconButton
                            size="small"
                            color="error"
                            onClick={() => handleRevokeKey(key.key_id)}
                            disabled={key.status === 'revoked'}
                          >
                            <DeleteIcon />
                          </IconButton>
                        </Tooltip>
                      </Box>
                    </TableCell>
                  </TableRow>
                ))}
            </TableBody>
          </Table>
        )}
      </TableContainer>

      {/* 新規APIキー作成ダイアログ */}
      <Dialog open={openDialog} onClose={() => setOpenDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>新規APIキー作成</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
            <FormControl fullWidth>
              <InputLabel>サービス</InputLabel>
              <Select
                value={newKey.service}
                onChange={(e) => setNewKey({ ...newKey, service: e.target.value })}
                label="サービス"
              >
                {services.map((service) => (
                  <MenuItem key={service.value} value={service.value}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <span>{service.icon}</span>
                      <span>{service.label}</span>
                    </Box>
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <TextField
              label="キー名"
              value={newKey.name}
              onChange={(e) => setNewKey({ ...newKey, name: e.target.value })}
              fullWidth
              placeholder="例: Production API Key"
            />

            {newKey.service === 'stripe' && (
              <TextField
                label="Stripe APIキー"
                value={newKey.credentials.api_key || ''}
                onChange={(e) =>
                  setNewKey({
                    ...newKey,
                    credentials: { ...newKey.credentials, api_key: e.target.value },
                  })
                }
                fullWidth
                type="password"
                placeholder="sk_live_..."
              />
            )}

            {newKey.service === 'shopify' && (
              <>
                <TextField
                  label="Shopify APIキー"
                  value={newKey.credentials.api_key || ''}
                  onChange={(e) =>
                    setNewKey({
                      ...newKey,
                      credentials: { ...newKey.credentials, api_key: e.target.value },
                    })
                  }
                  fullWidth
                  type="password"
                />
                <TextField
                  label="ショップドメイン"
                  value={newKey.credentials.shop_domain || ''}
                  onChange={(e) =>
                    setNewKey({
                      ...newKey,
                      credentials: {
                        ...newKey.credentials,
                        shop_domain: e.target.value,
                      },
                    })
                  }
                  fullWidth
                  placeholder="myshop.myshopify.com"
                />
              </>
            )}

            {newKey.service === 'github' && (
              <TextField
                label="GitHub Personal Access Token"
                value={newKey.credentials.personal_access_token || ''}
                onChange={(e) =>
                  setNewKey({
                    ...newKey,
                    credentials: {
                      ...newKey.credentials,
                      personal_access_token: e.target.value,
                    },
                  })
                }
                fullWidth
                type="password"
                placeholder="ghp_..."
              />
            )}

            <FormControlLabel
              control={
                <Switch
                  checked={newKey.auto_renew}
                  onChange={(e) =>
                    setNewKey({ ...newKey, auto_renew: e.target.checked })
                  }
                />
              }
              label="自動更新を有効にする"
            />

            <Alert severity="info">
              APIキーは暗号化されて安全に保存されます。キーの実際の値は作成後に確認できません。
            </Alert>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenDialog(false)}>キャンセル</Button>
          <Button
            onClick={handleCreateKey}
            variant="contained"
            disabled={!newKey.service || !newKey.name}
          >
            作成
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};