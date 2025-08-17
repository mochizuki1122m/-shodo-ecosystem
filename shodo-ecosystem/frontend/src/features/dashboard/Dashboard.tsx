import {
  Box,
  Grid,
  Paper,
  Typography,
  Card,
  CardContent,
  CardActions,
  Button,
  Chip,
  LinearProgress,
  List,
  ListItem,
  ListItemText,
  Avatar,
} from '@mui/material';
import {
  ShoppingBag as ShopifyIcon,
  Email as GmailIcon,
  Payment as StripeIcon,
  Message as SlackIcon,
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  TrendingUp as TrendingUpIcon,
  Speed as SpeedIcon,
} from '@mui/icons-material';
import { useQuery } from '@tanstack/react-query';
// import { getDetectedServices } from '../../services/api';

// サービスアイコンマッピング
// const serviceIcons: Record<string, React.ReactNode> = {
//   shopify: <ShopifyIcon />,
//   gmail: <GmailIcon />,
//   stripe: <StripeIcon />,
//   slack: <SlackIcon />,
// };

// モックデータ（実際はAPIから取得）
const mockServices = [
  {
    id: 'shopify-1',
    name: 'Shopify',
    icon: '🛍️',
    status: 'connected',
    isLoggedIn: true,
    lastSync: '5分前',
    stats: {
      orders: 156,
      products: 423,
      customers: 1289,
    },
  },
  {
    id: 'gmail-1',
    name: 'Gmail',
    icon: '📧',
    status: 'connected',
    isLoggedIn: true,
    lastSync: '1分前',
    stats: {
      unread: 12,
      total: 3456,
      sent: 234,
    },
  },
  {
    id: 'stripe-1',
    name: 'Stripe',
    icon: '💳',
    status: 'connected',
    isLoggedIn: true,
    lastSync: '10分前',
    stats: {
      revenue: '¥1,234,567',
      transactions: 89,
      subscriptions: 45,
    },
  },
  {
    id: 'slack-1',
    name: 'Slack',
    icon: '💬',
    status: 'disconnected',
    isLoggedIn: false,
    lastSync: null,
    stats: null,
  },
];

const Dashboard: React.FC = () => {
  // 実際のAPIコール（現在はモックデータを使用）
  const { data: services = mockServices, isLoading } = useQuery({
    queryKey: ['services'],
    queryFn: async () => {
      // return await getDetectedServices();
      return mockServices; // 開発中はモックデータを使用
    },
    refetchInterval: 30000, // 30秒ごとに更新
  });

  const connectedServices = services.filter(s => s.status === 'connected').length;
  const totalServices = services.length;

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        ダッシュボード
      </Typography>
      
      {/* 統計カード */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Paper sx={{ p: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
              <CheckCircleIcon color="success" sx={{ mr: 1 }} />
              <Typography variant="subtitle2" color="text.secondary">
                接続済みサービス
              </Typography>
            </Box>
            <Typography variant="h4">
              {connectedServices}/{totalServices}
            </Typography>
            <LinearProgress
              variant="determinate"
              value={(connectedServices / totalServices) * 100}
              sx={{ mt: 1 }}
            />
          </Paper>
        </Grid>
        
        <Grid item xs={12} sm={6} md={3}>
          <Paper sx={{ p: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
              <SpeedIcon color="primary" sx={{ mr: 1 }} />
              <Typography variant="subtitle2" color="text.secondary">
                処理速度
              </Typography>
            </Box>
            <Typography variant="h4">0.2秒</Typography>
            <Typography variant="caption" color="success.main">
              15倍高速化達成
            </Typography>
          </Paper>
        </Grid>
        
        <Grid item xs={12} sm={6} md={3}>
          <Paper sx={{ p: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
              <TrendingUpIcon color="info" sx={{ mr: 1 }} />
              <Typography variant="subtitle2" color="text.secondary">
                本日の処理数
              </Typography>
            </Box>
            <Typography variant="h4">1,234</Typography>
            <Typography variant="caption" color="text.secondary">
              前日比 +23%
            </Typography>
          </Paper>
        </Grid>
        
        <Grid item xs={12} sm={6} md={3}>
          <Paper sx={{ p: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
              <WarningIcon color="warning" sx={{ mr: 1 }} />
              <Typography variant="subtitle2" color="text.secondary">
                エラー率
              </Typography>
            </Box>
            <Typography variant="h4">0.3%</Typography>
            <Typography variant="caption" color="success.main">
              正常範囲内
            </Typography>
          </Paper>
        </Grid>
      </Grid>
      
      {/* サービス一覧 */}
      <Typography variant="h5" gutterBottom sx={{ mt: 4, mb: 2 }}>
        連携サービス
      </Typography>
      
      {isLoading ? (
        <LinearProgress />
      ) : (
        <Grid container spacing={3}>
          {services.map((service) => (
            <Grid item xs={12} sm={6} md={4} key={service.id}>
              <Card>
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                    <Avatar sx={{ bgcolor: 'primary.main', mr: 2 }}>
                      {service.icon}
                    </Avatar>
                    <Box sx={{ flexGrow: 1 }}>
                      <Typography variant="h6">{service.name}</Typography>
                      <Chip
                        label={service.status === 'connected' ? '接続中' : '未接続'}
                        color={service.status === 'connected' ? 'success' : 'default'}
                        size="small"
                      />
                    </Box>
                  </Box>
                  
                  {service.isLoggedIn && service.stats && (
                    <List dense>
                      {Object.entries(service.stats).map(([key, value]) => (
                        <ListItem key={key} disableGutters>
                          <ListItemText
                            primary={key}
                            secondary={value}
                            primaryTypographyProps={{ variant: 'caption' }}
                            secondaryTypographyProps={{ variant: 'body2' }}
                          />
                        </ListItem>
                      ))}
                    </List>
                  )}
                  
                  {service.lastSync && (
                    <Typography variant="caption" color="text.secondary">
                      最終同期: {service.lastSync}
                    </Typography>
                  )}
                </CardContent>
                
                <CardActions>
                  {service.status === 'connected' ? (
                    <>
                      <Button size="small">詳細</Button>
                      <Button size="small" color="error">切断</Button>
                    </>
                  ) : (
                    <Button size="small" variant="contained">
                      接続
                    </Button>
                  )}
                </CardActions>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}
      
      {/* 使い方ガイド */}
      <Paper sx={{ p: 3, mt: 4, bgcolor: 'info.main', color: 'white' }}>
        <Typography variant="h6" gutterBottom>
          クイックスタート
        </Typography>
        <Typography variant="body2" paragraph>
          1. 左メニューから「自然言語入力」を選択
        </Typography>
        <Typography variant="body2" paragraph>
          2. 日本語で操作したい内容を入力（例：「Shopifyの今月の売上を確認」）
        </Typography>
        <Typography variant="body2" paragraph>
          3. AIが意図を理解し、自動的に処理を実行
        </Typography>
        <Typography variant="body2">
          💡 ヒント: 曖昧な指示でも、AIが文脈を理解して適切な提案をします
        </Typography>
      </Paper>
    </Box>
  );
};

export default Dashboard;