import { Navigate } from 'react-router-dom'

import { canAccessFeature, type FeatureKey } from '@ai-invest/shared'

import { useAuthStore } from '@/stores/auth'

interface RequireFeatureProps {
  feature: FeatureKey
  children: React.ReactNode
}

/** 功能模块路由守卫：无权限 → 工作台（admin 不受限）。 */
export function RequireFeature({ feature, children }: RequireFeatureProps) {
  const user = useAuthStore((s) => s.user)

  if (!canAccessFeature(user, feature)) {
    return <Navigate to="/workbench" replace />
  }

  return <>{children}</>
}
