import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { AgentOverview } from './AgentOverview'

vi.mock('@/hooks/useTradingAgent', async () => {
  const { makeOverviewItem } = await import('./testFixtures')
  return {
    useAgentOverview: () => ({ data: { items: [makeOverviewItem()] }, isLoading: false }),
    useLiveAgentObservations: () => ({ data: undefined, isLoading: false }),
    useUpdateTradingAgentConfig: () => ({ mutate: vi.fn(), isPending: false }),
    useDeleteTradingAgent: () => ({ mutate: vi.fn(), isPending: false, variables: null }),
    useCreateTradingAgent: () => ({ mutate: vi.fn(), isPending: false }),
    useTradingAgentPromptTemplates: () => ({ data: [] }),
  }
})
vi.mock('@/hooks/useSystemStatus', () => ({ useSystemStatus: () => ({ data: undefined }) }))
vi.mock('@/hooks/useCeleryQueues', () => ({ useCeleryQueues: () => ({ data: undefined }) }))

describe('AgentOverview', () => {
  it('页面直render主板与决策流，无底部管理折叠面板', () => {
    render(
      <MemoryRouter>
        <AgentOverview />
      </MemoryRouter>,
    )
    expect(screen.getByText('RV-ENGINE-01')).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('右上角图标按钮打开 Agent 管理对话框（增删改入口）', () => {
    render(
      <MemoryRouter>
        <AgentOverview />
      </MemoryRouter>,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Agent 管理' }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('新建 Agent')).toBeInTheDocument()
    expect(screen.getAllByText('短线猎手').length).toBeGreaterThanOrEqual(2)
    fireEvent.click(screen.getByRole('button', { name: /close/i }))
    expect(screen.queryByRole('dialog')).toBeNull()
  })
})
