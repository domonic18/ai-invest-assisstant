import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { useAuthStore } from './auth'

function TestComponent() {
  const { user, isAdmin, token } = useAuthStore()
  return (
    <div>
      <span data-testid="user">{user?.username || 'none'}</span>
      <span data-testid="admin">{isAdmin ? 'yes' : 'no'}</span>
      <span data-testid="token">{token || 'none'}</span>
    </div>
  )
}

describe('auth store', () => {
  it('initializes with no token', () => {
    localStorage.removeItem('access_token')
    render(<TestComponent />)
    expect(screen.getByTestId('token')).toHaveTextContent('none')
  })

  it('reflects login state', () => {
    const store = useAuthStore.getState()
    store.login('token123', { id: '1', username: 'tester', email: 'test@example.com', isAdmin: true })
    expect(useAuthStore.getState().token).toBe('token123')
    expect(useAuthStore.getState().isAdmin).toBe(true)
    store.logout()
    expect(useAuthStore.getState().token).toBeNull()
  })
})
