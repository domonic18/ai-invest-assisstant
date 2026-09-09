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
const AdminTasks = lazy(() => import('./pages/Admin/Tasks/Tasks').then((m) => ({ default: m.AdminTasks })))
const AdminUsers = lazy(() => import('./pages/Admin/Users/Users').then((m) => ({ default: m.AdminUsers })))
const Collector = lazy(() => import('./pages/Admin/Collector').then((m) => ({ default: m.Collector })))
const CollectorChannelConfig = lazy(() =>
  import('./pages/Admin/CollectorChannelConfig/CollectorChannelConfig').then((m) => ({
    default: m.CollectorChannelConfig,
  })),
)
const LLMConfig = lazy(() => import('./pages/Admin/LLMConfig/LLMConfig').then((m) => ({ default: m.LLMConfig })))
const ProxyConfig = lazy(() =>
  import('./pages/Admin/ProxyConfig/ProxyConfig').then((m) => ({ default: m.ProxyConfig })),
)
const AiResultsAdmin = lazy(() =>
  import('./pages/Admin/AiResults/AiResultsAdmin').then((m) => ({
    default: m.AiResultsAdmin,
  })),
)
const TrackedIndex = lazy(() =>
  import('./pages/Admin/TrackedIndex/TrackedIndex').then((m) => ({ default: m.TrackedIndex })),
)
const AuctionReview = lazy(() =>
  import('./pages/AuctionReview/AuctionReview').then((m) => ({ default: m.AuctionReview })),
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
const Register = lazy(() => import('./pages/Register/Register').then((m) => ({ default: m.Register })))
const Settings = lazy(() => import('./pages/Settings/Settings').then((m) => ({ default: m.Settings })))
const SkillsPage = lazy(() => import('./pages/Skills/SkillsPage').then((m) => ({ default: m.SkillsPage })))
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
      // 旧路由兜底：电报视图已迁入资讯中心（迭代 3）
      { path: 'telegraph', element: <Navigate to="/news" replace /> },
      { path: 'financial/:code', element: lazyEl(<Financial />) },
      { path: 'settings', element: lazyEl(<Settings />) },
      { path: 'skills', element: lazyEl(<SkillsPage />) },
      { path: 'watchlist', element: lazyEl(<Watchlist />) },
      {
        path: 'admin',
        element: <ProtectedAdmin />,
        children: [
          { index: true, element: lazyEl(<Admin />) },
          { path: 'users', element: lazyEl(<AdminUsers />) },
          { path: 'stocks', element: lazyEl(<AdminStocks />) },
          { path: 'reports', element: lazyEl(<AdminReports />) },
          { path: 'news', element: lazyEl(<AdminNews />) },
          { path: 'tasks', element: lazyEl(<AdminTasks />) },
          { path: 'llm-configs', element: lazyEl(<LLMConfig />) },
          { path: 'proxy-configs', element: lazyEl(<ProxyConfig />) },
          { path: 'ai-results', element: lazyEl(<AiResultsAdmin />) },
          { path: 'tracked-indexes', element: lazyEl(<TrackedIndex />) },
          { path: 'collector-channels', element: lazyEl(<CollectorChannelConfig />) },
          { path: 'collector', element: lazyEl(<Collector />) },
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
