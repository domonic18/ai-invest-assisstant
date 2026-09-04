import { Layout } from '@/components/layout/Layout'

import { RequireAuth } from './RequireAuth'

export function ProtectedLayout() {
  return (
    <RequireAuth>
      <Layout />
    </RequireAuth>
  )
}
