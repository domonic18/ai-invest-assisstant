import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useAuthStore } from './auth'

vi.mock('@/api/auth', () => ({
  fetchCurrentUser: vi.fn(),
}))

const { fetchCurrentUser } = vi.mocked(await import('@/api/auth'))
const mockFetchCurrentUser = vi.mocked(fetchCurrentUser)

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

describe('auth store 初始化容错', () => {
  beforeEach(() => {
    mockFetchCurrentUser.mockReset()
    useAuthStore.setState({
      token: null,
      user: null,
      isInitialized: false,
      isLoading: false,
      error: null,
      initError: null,
      isAdmin: false,
    })
  })

  it('initialize 遇 502 保留 token 并置 initError', async () => {
    localStorage.setItem('access_token', 'tok502')
    useAuthStore.setState({ token: 'tok502' })
    mockFetchCurrentUser.mockRejectedValueOnce(
      Object.assign(new Error('冷启动 502'), { status: 502 })
    )

    await useAuthStore.getState().initialize()

    const state = useAuthStore.getState()
    expect(state.token).toBe('tok502')
    expect(state.isInitialized).toBe(true)
    expect(state.initError).toBe('冷启动 502')
    expect(localStorage.getItem('access_token')).toBe('tok502')
  })

  it('initialize 遇 401 清除会话', async () => {
    localStorage.setItem('access_token', 'tok401')
    useAuthStore.setState({ token: 'tok401' })
    mockFetchCurrentUser.mockRejectedValueOnce({ response: { status: 401 } })

    await useAuthStore.getState().initialize()

    const state = useAuthStore.getState()
    expect(state.token).toBeNull()
    expect(localStorage.getItem('access_token')).toBeNull()
    expect(state.error).toBeTruthy()
  })

  it('initialize 成功后清除 initError', async () => {
    localStorage.setItem('access_token', 'tok-ok')
    useAuthStore.setState({ token: 'tok-ok', initError: '上一次失败' })
    mockFetchCurrentUser.mockResolvedValueOnce({
      id: '1',
      username: 'tester',
      email: 't@e.com',
      isAdmin: false,
    })

    await useAuthStore.getState().initialize()

    const state = useAuthStore.getState()
    expect(state.user?.username).toBe('tester')
    expect(state.initError).toBeNull()
  })
})
