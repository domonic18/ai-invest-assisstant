import { Navigate, useLocation } from 'react-router-dom'

import { useAuthStore } from '@/stores/auth'

interface RequireAuthProps {
  children: React.ReactNode
  requireAdmin?: boolean
}

export function RequireAuth({ children, requireAdmin = false }: RequireAuthProps) {
  const { token, user, isInitialized, initError, isLoading, initialize } = useAuthStore()
  const location = useLocation()

  if (!isInitialized) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0c0e12] text-white">
        加载中...
      </div>
    )
  }

  if (!token) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (!user) {
    // token 仍在但用户信息加载失败（非 401，如冷启动 502）：手动重试而非强制登出
    if (initError) {
      return (
        <div className="min-h-screen flex flex-col items-center justify-center gap-4 bg-[#0c0e12] text-white">
          <div>页面加载失败：{initError}</div>
          <button
            type="button"
            onClick={() => initialize()}
            disabled={isLoading}
            className="px-4 py-2 rounded-md bg-[#5e6ad2] text-white text-sm disabled:opacity-60"
          >
            {isLoading ? '重试中...' : '重试'}
          </button>
        </div>
      )
    }
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0c0e12] text-white">
        加载中...
      </div>
    )
  }

  if (requireAdmin && !user.isAdmin) {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}
