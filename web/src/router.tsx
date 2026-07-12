import { createBrowserRouter } from 'react-router-dom'
import { Layout } from './components/layout/Layout'
import { Dashboard } from './pages/Dashboard/Dashboard'
import { ChainAnalysis } from './pages/ChainAnalysis/ChainAnalysis'
import { StockDetail } from './pages/StockDetail/StockDetail'
import { Hotspot } from './pages/Hotspot/Hotspot'
import { CapitalFlow } from './pages/CapitalFlow/CapitalFlow'
import { AuctionReview } from './pages/AuctionReview/AuctionReview'
import { Research } from './pages/Research/Research'
import { Settings } from './pages/Settings/Settings'
import { Login } from './pages/Login/Login'
import { Register } from './pages/Register/Register'
import { Admin } from './pages/Admin/Admin'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: 'chain/:industry?', element: <ChainAnalysis /> },
      { path: 'stock/:code', element: <StockDetail /> },
      { path: 'hotspot', element: <Hotspot /> },
      { path: 'capital-flow', element: <CapitalFlow /> },
      { path: 'auction', element: <AuctionReview /> },
      { path: 'research', element: <Research /> },
      { path: 'settings', element: <Settings /> },
      { path: 'admin', element: <Admin /> },
    ],
  },
  { path: '/login', element: <Login /> },
  { path: '/register', element: <Register /> },
])
