import { Outlet } from 'react-router-dom'

import { RequireAuth } from './RequireAuth'

export function ProtectedAdmin() {
  return (
    <RequireAuth requireAdmin>
      <Outlet />
    </RequireAuth>
  )
}
