import { Navigate } from 'react-router-dom'

import { useAuthStore } from '@/stores/auth'

interface RedirectIfAuthenticatedProps {
  children: React.ReactNode
}

export function RedirectIfAuthenticated({ children }: RedirectIfAuthenticatedProps) {
  const { token, isInitialized } = useAuthStore()

  if (!isInitialized) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0c0e12] text-white">
        加载中...
      </div>
    )
  }

  if (token) {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}
