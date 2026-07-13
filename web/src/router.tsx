import { createBrowserRouter, Navigate } from 'react-router-dom'

import { ProtectedAdmin } from './components/auth/ProtectedAdmin'
import { ProtectedLayout } from './components/auth/ProtectedLayout'
import { RedirectIfAuthenticated } from './components/auth/RedirectIfAuthenticated'
import { Admin } from './pages/Admin/Admin'
import { AuctionReview } from './pages/AuctionReview/AuctionReview'
import { CapitalFlow } from './pages/CapitalFlow/CapitalFlow'
import { ChainAnalysis } from './pages/ChainAnalysis/ChainAnalysis'
import { Collector } from './pages/Admin/Collector'
import { CollectorChannelConfig } from './pages/Admin/CollectorChannelConfig/CollectorChannelConfig'
import { Dashboard } from './pages/Dashboard/Dashboard'
import { Hotspot } from './pages/Hotspot/Hotspot'
import { LLMConfig } from './pages/Admin/LLMConfig/LLMConfig'
import { Login } from './pages/Login/Login'
import { Register } from './pages/Register/Register'
import { Research } from './pages/Research/Research'
import { Settings } from './pages/Settings/Settings'
import { StockDetail } from './pages/StockDetail/StockDetail'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <ProtectedLayout />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: 'chain/:industry?', element: <ChainAnalysis /> },
      { path: 'stock/:code', element: <StockDetail /> },
      { path: 'hotspot', element: <Hotspot /> },
      { path: 'capital-flow', element: <CapitalFlow /> },
      { path: 'auction', element: <AuctionReview /> },
      { path: 'research', element: <Research /> },
      { path: 'settings', element: <Settings /> },
      {
        path: 'admin',
        element: <ProtectedAdmin />,
        children: [
          { index: true, element: <Admin /> },
          { path: 'llm-configs', element: <LLMConfig /> },
          { path: 'collector-channels', element: <CollectorChannelConfig /> },
          { path: 'collector', element: <Collector /> },
        ],
      },
    ],
  },
  {
    path: '/login',
    element: (
      <RedirectIfAuthenticated>
        <Login />
      </RedirectIfAuthenticated>
    ),
  },
  {
    path: '/register',
    element: (
      <RedirectIfAuthenticated>
        <Register />
      </RedirectIfAuthenticated>
    ),
  },
  { path: '*', element: <Navigate to="/" replace /> },
])
