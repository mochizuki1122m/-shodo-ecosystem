/**
 * LPR同意UIコンポーネント
 * 
 * ユーザーにLPRトークンの発行について明示的な同意を求めるUI
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  FormControl,
  FormControlLabel,
  FormGroup,
  FormHelperText,
  Grid,
  IconButton,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Paper,
  Slider,
  Typography,
  Alert,
  AlertTitle,
  Chip,
  Divider,
  Tooltip,
  LinearProgress,
} from '@mui/material';
import {
  Security as SecurityIcon,
  Lock as LockIcon,
  Timer as TimerIcon,
  DeviceHub as DeviceIcon,
  Policy as PolicyIcon,
  Info as InfoIcon,
  Warning as WarningIcon,
  CheckCircle as CheckIcon,
  Cancel as CancelIcon,
  Visibility as VisibilityIcon,
  VisibilityOff as VisibilityOffIcon,
  Fingerprint as FingerprintIcon,
  Speed as SpeedIcon,
  Block as BlockIcon,
} from '@mui/icons-material';

// デバイス指紋を収集
const collectDeviceFingerprint = (): any => {
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  if (ctx) {
    ctx.textBaseline = 'top';
    ctx.font = '14px Arial';
    ctx.fillText('fingerprint', 2, 2);
  }
  const canvasData = canvas.toDataURL();

  return {
    userAgent: navigator.userAgent,
    acceptLanguage: navigator.language,
    screenResolution: `${screen.width}x${screen.height}`,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    platform: navigator.platform,
    hardwareConcurrency: navigator.hardwareConcurrency,
    deviceMemory: (navigator as any).deviceMemory,
    canvasFingerprint: canvasData.substring(0, 50),
  };
};

interface LPRScope {
  method: string;
  url_pattern: string;
  description?: string;
  required?: boolean;
}

interface LPRPolicy {
  rate_limit_rps: number;
  rate_limit_burst: number;
  human_speed_jitter: boolean;
  require_device_match: boolean;
  allow_concurrent: boolean;
  max_request_size: number;
}

interface LPRConsentProps {
  open: boolean;
  onClose: () => void;
  onConsent: (params: LPRConsentParams) => void;
  serviceName: string;
  serviceUrl: string;
  suggestedScopes?: LPRScope[];
  suggestedTTL?: number;
  suggestedOrigins?: string[];
}

interface LPRConsentParams {
  scopes: LPRScope[];
  origins: string[];
  ttl_seconds: number;
  policy: LPRPolicy;
  device_fingerprint: any;
  purpose: string;
  consent: boolean;
}

export const LPRConsentDialog: React.FC<LPRConsentProps> = ({
  open,
  onClose,
  onConsent,
  serviceName,
  serviceUrl,
  suggestedScopes = [],
  suggestedTTL = 3600,
  suggestedOrigins = [],
}) => {
  const [selectedScopes, setSelectedScopes] = useState<Set<number>>(new Set());
  const [ttlMinutes, setTtlMinutes] = useState(suggestedTTL / 60);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [policy, setPolicy] = useState<LPRPolicy>({
    rate_limit_rps: 1.0,
    rate_limit_burst: 10,
    human_speed_jitter: true,
    require_device_match: true,
    allow_concurrent: false,
    max_request_size: 10485760,
  });
  const [deviceFingerprint, setDeviceFingerprint] = useState<any>(null);
  const [consentChecked, setConsentChecked] = useState(false);

  useEffect(() => {
    if (open) {
      // デバイス指紋を収集
      const fingerprint = collectDeviceFingerprint();
      setDeviceFingerprint(fingerprint);
      
      // デフォルトで必須スコープを選択
      const requiredIndices = new Set<number>();
      suggestedScopes.forEach((scope, index) => {
        if (scope.required) {
          requiredIndices.add(index);
        }
      });
      setSelectedScopes(requiredIndices);
    }
  }, [open, suggestedScopes]);

  const handleScopeToggle = (index: number) => {
    const scope = suggestedScopes[index];
    if (scope.required) {
      // 必須スコープは選択解除不可
      return;
    }
    
    const newSelected = new Set(selectedScopes);
    if (newSelected.has(index)) {
      newSelected.delete(index);
    } else {
      newSelected.add(index);
    }
    setSelectedScopes(newSelected);
  };

  const handleConsent = () => {
    const selectedScopesList = Array.from(selectedScopes).map(
      index => suggestedScopes[index]
    );

    onConsent({
      scopes: selectedScopesList,
      origins: suggestedOrigins,
      ttl_seconds: ttlMinutes * 60,
      policy,
      device_fingerprint: deviceFingerprint,
      purpose: `Access to ${serviceName}`,
      consent: true,
    });
  };

  const formatTTL = (minutes: number): string => {
    if (minutes < 60) {
      return `${minutes}分`;
    } else if (minutes < 1440) {
      return `${Math.floor(minutes / 60)}時間`;
    } else {
      return `${Math.floor(minutes / 1440)}日`;
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: 2,
        },
      }}
      data-testid="lpr-consent"
    >
      <DialogTitle sx={{ pb: 1 }}>
        <Box display="flex" alignItems="center" gap={1}>
          <SecurityIcon color="primary" />
          <Typography variant="h6">限定代理権限（LPR）の付与</Typography>
        </Box>
      </DialogTitle>
      
      <DialogContent dividers>
        <Box sx={{ mb: 3 }}>
          <Alert severity="info" sx={{ mb: 2 }}>
            <AlertTitle>安全な代理実行について</AlertTitle>
            <Typography variant="body2">
              {serviceName}へのアクセスを安全に代理実行するため、限定的な権限（LPR）を発行します。
              この権限は指定された範囲と期間のみ有効で、いつでも取り消すことができます。
            </Typography>
          </Alert>

          <Paper elevation={0} sx={{ p: 2, bgcolor: 'grey.50', mb: 2 }}>
            <Typography variant="subtitle2" gutterBottom>
              対象サービス
            </Typography>
            <Typography variant="body1" sx={{ fontWeight: 'medium' }}>
              {serviceName}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {serviceUrl}
            </Typography>
          </Paper>

          {/* スコープ選択 */}
          <Box sx={{ mb: 3 }}>
            <Typography variant="subtitle1" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <PolicyIcon fontSize="small" />
              許可する操作
            </Typography>
            <FormGroup>
              {suggestedScopes.map((scope, index) => (
                <FormControlLabel
                  key={index}
                  control={
                    <Checkbox
                      checked={selectedScopes.has(index)}
                      onChange={() => handleScopeToggle(index)}
                      disabled={scope.required}
                    />
                  }
                  label={
                    <Box>
                      <Box display="flex" alignItems="center" gap={1}>
                        <Chip
                          label={scope.method}
                          size="small"
                          color={scope.method === 'GET' ? 'info' : 'warning'}
                          sx={{ fontSize: '0.7rem' }}
                        />
                        <Typography variant="body2">
                          {scope.url_pattern}
                        </Typography>
                        {scope.required && (
                          <Chip label="必須" size="small" color="error" sx={{ fontSize: '0.7rem' }} />
                        )}
                      </Box>
                      {scope.description && (
                        <Typography variant="caption" color="text.secondary">
                          {scope.description}
                        </Typography>
                      )}
                    </Box>
                  }
                />
              ))}
            </FormGroup>
          </Box>

          {/* 有効期限 */}
          <Box sx={{ mb: 3 }}>
            <Typography variant="subtitle1" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <TimerIcon fontSize="small" />
              有効期限: {formatTTL(ttlMinutes)}
            </Typography>
            <Slider
              value={ttlMinutes}
              onChange={(_, value) => setTtlMinutes(value as number)}
              min={5}
              max={1440}
              step={5}
              marks={[
                { value: 5, label: '5分' },
                { value: 60, label: '1時間' },
                { value: 360, label: '6時間' },
                { value: 1440, label: '24時間' },
              ]}
              valueLabelDisplay="auto"
              valueLabelFormat={formatTTL}
            />
          </Box>

          {/* デバイス情報 */}
          <Box sx={{ mb: 3 }}>
            <Typography variant="subtitle1" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <DeviceIcon fontSize="small" />
              デバイス拘束
            </Typography>
            <Paper elevation={0} sx={{ p: 1.5, bgcolor: 'grey.50' }}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                このLPRトークンは現在のデバイスでのみ有効です
              </Typography>
              {deviceFingerprint && (
                <Box sx={{ mt: 1 }}>
                  <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
                    <FingerprintIcon fontSize="small" sx={{ verticalAlign: 'middle', mr: 0.5 }} />
                    {deviceFingerprint.platform} / {deviceFingerprint.screenResolution}
                  </Typography>
                </Box>
              )}
            </Paper>
          </Box>

          {/* 高度な設定 */}
          <Box>
            <Button
              onClick={() => setShowAdvanced(!showAdvanced)}
              endIcon={showAdvanced ? <VisibilityOffIcon /> : <VisibilityIcon />}
              size="small"
            >
              高度な設定
            </Button>
            
            {showAdvanced && (
              <Paper elevation={0} sx={{ p: 2, mt: 2, bgcolor: 'grey.50' }}>
                <Grid container spacing={2}>
                  <Grid item xs={12} sm={6}>
                    <FormControlLabel
                      control={
                        <Checkbox
                          checked={policy.human_speed_jitter}
                          onChange={(e) => setPolicy({ ...policy, human_speed_jitter: e.target.checked })}
                        />
                      }
                      label={
                        <Box>
                          <Typography variant="body2">
                            <SpeedIcon fontSize="small" sx={{ verticalAlign: 'middle', mr: 0.5 }} />
                            人間的速度制御
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            自然な操作速度を維持
                          </Typography>
                        </Box>
                      }
                    />
                  </Grid>
                  
                  <Grid item xs={12} sm={6}>
                    <FormControlLabel
                      control={
                        <Checkbox
                          checked={policy.require_device_match}
                          onChange={(e) => setPolicy({ ...policy, require_device_match: e.target.checked })}
                        />
                      }
                      label={
                        <Box>
                          <Typography variant="body2">
                            <DeviceIcon fontSize="small" sx={{ verticalAlign: 'middle', mr: 0.5 }} />
                            デバイス検証
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            デバイス変更を検出
                          </Typography>
                        </Box>
                      }
                    />
                  </Grid>
                  
                  <Grid item xs={12}>
                    <Typography variant="body2" gutterBottom>
                      レート制限: {policy.rate_limit_rps} リクエスト/秒
                    </Typography>
                    <Slider
                      value={policy.rate_limit_rps}
                      onChange={(_, value) => setPolicy({ ...policy, rate_limit_rps: value as number })}
                      min={0.1}
                      max={10}
                      step={0.1}
                      valueLabelDisplay="auto"
                    />
                  </Grid>
                </Grid>
              </Paper>
            )}
          </Box>
        </Box>

        {/* セキュリティ情報 */}
        <Box sx={{ mt: 3 }}>
          <Typography variant="subtitle2" gutterBottom color="primary">
            <LockIcon fontSize="small" sx={{ verticalAlign: 'middle', mr: 0.5 }} />
            セキュリティ保証
          </Typography>
          <List dense>
            <ListItem>
              <ListItemIcon sx={{ minWidth: 32 }}>
                <CheckIcon fontSize="small" color="success" />
              </ListItemIcon>
              <ListItemText
                primary="最小権限の原則"
                secondary="必要最小限の権限のみを付与"
              />
            </ListItem>
            <ListItem>
              <ListItemIcon sx={{ minWidth: 32 }}>
                <CheckIcon fontSize="small" color="success" />
              </ListItemIcon>
              <ListItemText
                primary="時間制限"
                secondary="指定期間後に自動失効"
              />
            </ListItem>
            <ListItem>
              <ListItemIcon sx={{ minWidth: 32 }}>
                <CheckIcon fontSize="small" color="success" />
              </ListItemIcon>
              <ListItemText
                primary="監査ログ"
                secondary="すべての操作を記録"
              />
            </ListItem>
            <ListItem>
              <ListItemIcon sx={{ minWidth: 32 }}>
                <CheckIcon fontSize="small" color="success" />
              </ListItemIcon>
              <ListItemText
                primary="即時失効"
                secondary="いつでも取り消し可能"
              />
            </ListItem>
          </List>
        </Box>

        {/* 同意チェックボックス */}
        <Box sx={{ mt: 3 }}>
          <FormControlLabel
            control={
              <Checkbox
                checked={consentChecked}
                onChange={(e) => setConsentChecked(e.target.checked)}
                color="primary"
                inputProps={{ 'data-testid': 'consent-checkbox' }}
              />
            }
            label={
              <Typography variant="body2">
                上記の権限付与について理解し、同意します
              </Typography>
            }
          />
        </Box>
      </DialogContent>

      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={onClose} color="inherit">
          キャンセル
        </Button>
        <Button
          onClick={handleConsent}
          variant="contained"
          disabled={!consentChecked || selectedScopes.size === 0}
          startIcon={<SecurityIcon />}
          data-testid="grant-access"
        >
          権限を付与
        </Button>
      </DialogActions>
    </Dialog>
  );
};

// LPRトークン管理コンポーネント
export const LPRTokenManager: React.FC = () => {
  const [tokens, setTokens] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchTokens();
  }, []);

  const fetchTokens = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/v1/lpr/list', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      });
      const data = await response.json();
      setTokens(data.tokens || []);
    } catch (error) {
      console.error('Failed to fetch tokens:', error);
    } finally {
      setLoading(false);
    }
  };

  const revokeToken = async (jti: string) => {
    try {
      const response = await fetch('/api/v1/lpr/revoke', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
        body: JSON.stringify({
          jti,
          reason: 'User requested revocation',
        }),
      });
      
      if (response.ok) {
        fetchTokens();
      }
    } catch (error) {
      console.error('Failed to revoke token:', error);
    }
  };

  if (loading) {
    return <LinearProgress />;
  }

  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        アクティブなLPRトークン
      </Typography>
      
      {tokens.length === 0 ? (
        <Alert severity="info">
          アクティブなトークンはありません
        </Alert>
      ) : (
        <Grid container spacing={2}>
          {tokens.map((token) => (
            <Grid item xs={12} md={6} key={token.jti}>
              <Card>
                <CardHeader
                  title={token.service_name || 'Unknown Service'}
                  subheader={`発行: ${new Date(token.issued_at).toLocaleString()}`}
                  action={
                    <IconButton
                      onClick={() => revokeToken(token.jti)}
                      color="error"
                      size="small"
                    >
                      <BlockIcon />
                    </IconButton>
                  }
                />
                <CardContent>
                  <Typography variant="body2" color="text.secondary">
                    有効期限: {new Date(token.expires_at).toLocaleString()}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    スコープ: {token.scopes} 個
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    使用回数: {token.usage_count}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}
    </Box>
  );
};