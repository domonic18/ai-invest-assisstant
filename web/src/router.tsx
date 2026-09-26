import { lazy, Suspense, type ReactNode } from 'react'
import { createBrowserRouter, Navigate } from 'react-router-dom'

import { ProtectedAdmin } from './components/auth/ProtectedAdmin'
import { ProtectedLayout } from './components/auth/ProtectedLayout'
import { RedirectIfAuthenticated } from './components/auth/RedirectIfAuthenticated'
import { PageSkeleton } from './components/common/PageSkeleton'
import { Dashboard } from './pages/Dashboard/Dashboard'

const Admin = lazy(() => import('./pages/Admin/Admin').then((m) => ({ default: m.Admin })))
const AdminNews = lazy(() => import('./pages/Admin/News/News').then((m) => ({ default: m.AdminNews })))
const AdminReports = lazy(() => import('./pages/Admin/Reports/Reports').then((m) => ({ default: m.AdminReports })))
const AdminStocks = lazy(() => import('./pages/Admin/Stocks/Stocks').then((m) => ({ default: m.AdminStocks })))
const AdminUsers = lazy(() => import('./pages/Admin/Users/Users').then((m) => ({ default: m.AdminUsers })))
const CollectorAdmin = lazy(() =>
  import('./pages/Admin/Collector').then((m) => ({ default: m.CollectorAdmin })),
)
const ModelConfig = lazy(() => import('./pages/Admin/ModelConfig'))
const KnowledgeBase = lazy(() => import('./pages/Admin/KnowledgeBase'))
const KnowledgeSearchPage = lazy(() =>
  import('./pages/KnowledgeSearch').then((m) => ({ default: m.KnowledgeSearchPage }))
)
const McpServers = lazy(() =>
  import('./pages/Admin/McpServers/McpServers').then((m) => ({ default: m.McpServers })),
)
const ProxyConfig = lazy(() =>
  import('./pages/Admin/ProxyConfig/ProxyConfig').then((m) => ({ default: m.ProxyConfig })),
)
const SocialTracking = lazy(() =>
  import('./pages/Admin/SocialTracking/SocialTracking').then((m) => ({
    default: m.SocialTracking,
  })),
)
const SystemStatusPage = lazy(() =>
  import('./pages/Admin/SystemStatus/SystemStatus').then((m) => ({ default: m.SystemStatus })),
)
const TradeCalendarAdmin = lazy(() =>
  import('./pages/Admin/TradeCalendar/TradeCalendar').then((m) => ({ default: m.TradeCalendar })),
)
const UsageDashboard = lazy(() =>
  import('./pages/Admin/UsageDashboard/UsageDashboard').then((m) => ({ default: m.UsageDashboard })),
)
const AiResultsAdmin = lazy(() =>
  import('./pages/Admin/AiResults/AiResultsAdmin').then((m) => ({
    default: m.AiResultsAdmin,
  })),
)
const AuctionReview = lazy(() =>
  import('./pages/AuctionReview/AuctionReview').then((m) => ({ default: m.AuctionReview })),
)
const AnomalyPage = lazy(() =>
  import('./pages/Anomaly').then((m) => ({ default: m.AnomalyPage })),
)
const SectorDetailPage = lazy(() =>
  import('./pages/SectorDetail/SectorDetailPage').then((m) => ({ default: m.SectorDetailPage })),
)
const Calendar = lazy(() => import('./pages/Calendar').then((m) => ({ default: m.Calendar })))
const CapitalFlow = lazy(() => import('./pages/CapitalFlow/CapitalFlow').then((m) => ({ default: m.CapitalFlow })))
const ChainAnalysis = lazy(() =>
  import('./pages/ChainAnalysis/ChainAnalysis').then((m) => ({ default: m.ChainAnalysis })),
)
const Financial = lazy(() => import('./pages/Financial/Financial').then((m) => ({ default: m.Financial })))
const IndexDetail = lazy(() =>
  import('./pages/IndexDetail/IndexDetail').then((m) => ({ default: m.IndexDetail })),
)
const Login = lazy(() => import('./pages/Login/Login').then((m) => ({ default: m.Login })))
const MacroMonitor = lazy(() =>
  import('./pages/MacroMonitor/MacroMonitor').then((m) => ({ default: m.MacroMonitor })),
)
const News = lazy(() => import('./pages/News').then((m) => ({ default: m.News })))
const PaperTrade = lazy(() =>
  import('./pages/PaperTrade').then((m) => ({ default: m.PaperTrade })),
)
const PaperTradeAccountsAdmin = lazy(() =>
  import('./pages/Admin/PaperTradeAccounts').then((m) => ({
    default: m.PaperTradeAccountsAdmin,
  })),
)
const Register = lazy(() => import('./pages/Register/Register').then((m) => ({ default: m.Register })))
const ScreeningPage = lazy(() =>
  import('./pages/Screening/ScreeningPage').then((m) => ({ default: m.ScreeningPage })),
)
const Settings = lazy(() => import('./pages/Settings/Settings').then((m) => ({ default: m.Settings })))
const SkillsPage = lazy(() => import('./pages/Skills/SkillsPage').then((m) => ({ default: m.SkillsPage })))
const SkillDetailPage = lazy(() =>
  import('./pages/Skills/SkillDetailPage').then((m) => ({ default: m.SkillDetailPage })),
)
const StockDetail = lazy(() => import('./pages/StockDetail/StockDetail').then((m) => ({ default: m.StockDetail })))
const Watchlist = lazy(() => import('./pages/Watchlist').then((m) => ({ default: m.Watchlist })))
const Workbench = lazy(() =>
  import('./pages/Workbench/Workbench').then((m) => ({ default: m.Workbench })),
)

function lazyEl(node: ReactNode) {
  return <Suspense fallback={<PageSkeleton />}>{node}</Suspense>
}

export const router = createBrowserRouter([
  {
    path: '/',
    element: <ProtectedLayout />,
    children: [
      { index: true, element: <Navigate to="/workbench" replace /> },
      { path: 'workbench', element: lazyEl(<Workbench />) },
      { path: 'review', element: <Dashboard /> },
      // 异动检测合并页：板块/个股双 tab；子路径保持（page_event 跳转直达指定 tab）
      { path: 'anomaly', element: <Navigate to="/anomaly/sector" replace /> },
      { path: 'anomaly/sector', element: lazyEl(<AnomalyPage />) },
      { path: 'anomaly/stock', element: lazyEl(<AnomalyPage />) },
      // 板块详情：同花顺指数 K 线（板块名桥接）+ 资金流 + 异动日标注
      { path: 'sector/:sectorType/:sectorCode', element: lazyEl(<SectorDetailPage />) },
      { path: 'chain/:industry?', element: lazyEl(<ChainAnalysis />) },
      { path: 'stock/:code', element: lazyEl(<StockDetail />) },
      { path: 'capital-flow', element: lazyEl(<CapitalFlow />) },
      { path: 'macro-monitor', element: lazyEl(<MacroMonitor />) },
      // 指数详情：宏观监测/工作台指标卡点击进入（A 股 K 线 + 全球指标历史线）
      { path: 'index/:code', element: lazyEl(<IndexDetail />) },
      { path: 'auction-review', element: lazyEl(<AuctionReview />) },
      // 旧路由外链兜底：研报/财报入口并入个股详情右栏 tab（4.4.0）
      { path: 'auction', element: <Navigate to="/auction-review" replace /> },
      { path: 'hotspot', element: <Navigate to="/workbench" replace /> },
      { path: 'research', element: <Navigate to="/workbench" replace /> },
      { path: 'financial-reports', element: <Navigate to="/workbench" replace /> },
      { path: 'calendar', element: lazyEl(<Calendar />) },
      { path: 'news', element: lazyEl(<News />) },
      // 知识库搜索入口（搜索引擎式）：全员可问；?mediaId= 承载会话引用播放（凭证白名单校验）
      { path: 'kb', element: lazyEl(<KnowledgeSearchPage />) },
      // 旧路由兜底：电报视图已迁入资讯中心（迭代 3）
      { path: 'telegraph', element: <Navigate to="/news" replace /> },
      { path: 'financial/:code', element: lazyEl(<Financial />) },
      { path: 'settings', element: lazyEl(<Settings />) },
      { path: 'skills', element: lazyEl(<SkillsPage />) },
      { path: 'skills/:skillId', element: lazyEl(<SkillDetailPage />) },
      { path: 'watchlist', element: lazyEl(<Watchlist />) },
      // 模拟盘：掘金仿真只读展示（批次 2）；Agent 交易工具在批次 3 接入
      { path: 'paper-trade', element: lazyEl(<PaperTrade />) },
      // AI 选股：问财即席筛选，结果为 SPA 会话临时内容（迭代 6）
      { path: 'screening', element: lazyEl(<ScreeningPage />) },
      {
        path: 'admin',
        element: <ProtectedAdmin />,
        children: [
          { index: true, element: lazyEl(<Admin />) },
          { path: 'users', element: lazyEl(<AdminUsers />) },
          { path: 'usage-dashboard', element: lazyEl(<UsageDashboard />) },
          { path: 'stocks', element: lazyEl(<AdminStocks />) },
          { path: 'reports', element: lazyEl(<AdminReports />) },
          { path: 'news', element: lazyEl(<AdminNews />) },
          // 旧路由兜底：任务/渠道配置并入采集管理（tab 直达）
          { path: 'tasks', element: <Navigate to="/admin/collector?tab=tasks" replace /> },
          { path: 'model-configs', element: lazyEl(<ModelConfig />) },
          { path: 'llm-configs', element: <Navigate to="/admin/model-configs" replace /> },
          { path: 'knowledge-base', element: lazyEl(<KnowledgeBase />) },
          { path: 'mcp-servers', element: lazyEl(<McpServers />) },
          { path: 'social-tracking', element: lazyEl(<SocialTracking />) },
          { path: 'proxy-configs', element: lazyEl(<ProxyConfig />) },
          { path: 'ai-results', element: lazyEl(<AiResultsAdmin />) },
          { path: 'collector-channels', element: <Navigate to="/admin/collector?tab=channels" replace /> },
          { path: 'collector', element: lazyEl(<CollectorAdmin />) },
          { path: 'paper-trade', element: lazyEl(<PaperTradeAccountsAdmin />) },
          { path: 'system-status', element: lazyEl(<SystemStatusPage />) },
          { path: 'trade-calendar', element: lazyEl(<TradeCalendarAdmin />) },
        ],
      },
    ],
  },
  {
    path: '/login',
    element: (
      <RedirectIfAuthenticated>{lazyEl(<Login />)}</RedirectIfAuthenticated>
    ),
  },
  {
    path: '/register',
    element: (
      <RedirectIfAuthenticated>{lazyEl(<Register />)}</RedirectIfAuthenticated>
    ),
  },
  { path: '*', element: <Navigate to="/" replace /> },
])
