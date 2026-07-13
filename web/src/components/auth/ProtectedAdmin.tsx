import { AdminLayout } from '../layout/AdminLayout'
import { RequireAuth } from './RequireAuth'

export function ProtectedAdmin() {
  return (
    <RequireAuth requireAdmin>
      <AdminLayout />
    </RequireAuth>
  )
}
