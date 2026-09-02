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
const TrackedIndex = lazy(() =>
  import('./pages/Admin/TrackedIndex/TrackedIndex').then((m) => ({ default: m.TrackedIndex })),
)
const AuctionReview = lazy(() =>
  import('./pages/AuctionReview/AuctionReview').then((m) => ({ default: m.AuctionReview })),
)
const CapitalFlow = lazy(() => import('./pages/CapitalFlow/CapitalFlow').then((m) => ({ default: m.CapitalFlow })))
const ChainAnalysis = lazy(() =>
  import('./pages/ChainAnalysis/ChainAnalysis').then((m) => ({ default: m.ChainAnalysis })),
)
const Financial = lazy(() => import('./pages/Financial/Financial').then((m) => ({ default: m.Financial })))
const FinancialReportPage = lazy(() =>
  import('./pages/FinancialReport/FinancialReport').then((m) => ({ default: m.FinancialReportPage })),
)
const Hotspot = lazy(() => import('./pages/Hotspot/Hotspot').then((m) => ({ default: m.Hotspot })))
const Login = lazy(() => import('./pages/Login/Login').then((m) => ({ default: m.Login })))
const Register = lazy(() => import('./pages/Register/Register').then((m) => ({ default: m.Register })))
const Research = lazy(() => import('./pages/Research/Research').then((m) => ({ default: m.Research })))
const Settings = lazy(() => import('./pages/Settings/Settings').then((m) => ({ default: m.Settings })))
const StockDetail = lazy(() => import('./pages/StockDetail/StockDetail').then((m) => ({ default: m.StockDetail })))

function lazyEl(node: ReactNode) {
  return <Suspense fallback={<PageSkeleton />}>{node}</Suspense>
}

export const router = createBrowserRouter([
  {
    path: '/',
    element: <ProtectedLayout />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: 'chain/:industry?', element: lazyEl(<ChainAnalysis />) },
      { path: 'stock/:code', element: lazyEl(<StockDetail />) },
      { path: 'hotspot', element: lazyEl(<Hotspot />) },
      { path: 'capital-flow', element: lazyEl(<CapitalFlow />) },
      { path: 'auction', element: lazyEl(<AuctionReview />) },
      { path: 'research', element: lazyEl(<Research />) },
      { path: 'financial-reports', element: lazyEl(<FinancialReportPage />) },
      { path: 'financial/:code', element: lazyEl(<Financial />) },
      { path: 'settings', element: lazyEl(<Settings />) },
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
