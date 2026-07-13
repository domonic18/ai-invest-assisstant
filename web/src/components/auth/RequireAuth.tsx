import { Navigate, useLocation } from 'react-router-dom'

import { useAuthStore } from '@/stores/auth'

interface RequireAuthProps {
  children: React.ReactNode
  requireAdmin?: boolean
}

export function RequireAuth({ children, requireAdmin = false }: RequireAuthProps) {
  const { token, user, isInitialized } = useAuthStore()
  const location = useLocation()

  if (!isInitialized) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0c0e12] text-white">
        加载中...
      </div>
    )
  }

  if (!token || !user) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (requireAdmin && !user.isAdmin) {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}
