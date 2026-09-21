import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/kb', () => ({
  fetchKbConsumerSources: vi.fn(),
}))

vi.mock('@/pages/Admin/KnowledgeBase/SearchTab', () => ({
  SearchTab: (props: { consumerSources?: { id: number; name: string }[] }) => (
    <div data-testid="search-stub">
      {(props.consumerSources ?? []).map((s) => s.name).join(',')}
    </div>
  ),
}))

import { fetchKbConsumerSources } from '@/api/kb'

import { KnowledgeSearchPage } from './index'

const mockedSources = vi.mocked(fetchKbConsumerSources)

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return render(<KnowledgeSearchPage />, { wrapper })
}

describe('KnowledgeSearchPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders search tab with whitelist sources', async () => {
    mockedSources.mockResolvedValue([
      { id: 1, name: '课程库', sourceType: 'course' },
      { id: 2, name: '书库', sourceType: 'book' },
    ])
    renderPage()

    await waitFor(() => expect(screen.getByTestId('search-stub')).toBeInTheDocument())
    expect(screen.getByTestId('search-stub')).toHaveTextContent('课程库,书库')
    expect(screen.getByText('知识检索')).toBeInTheDocument()
  })

  it('403 renders authorization guidance', async () => {
    mockedSources.mockRejectedValue({ response: { status: 403 } })
    renderPage()

    await waitFor(() =>
      expect(screen.getByText('暂无知识库访问权限')).toBeInTheDocument()
    )
    expect(screen.queryByTestId('search-stub')).not.toBeInTheDocument()
  })

  it('other errors render generic failure', async () => {
    mockedSources.mockRejectedValue(new Error('boom'))
    renderPage()

    await waitFor(() =>
      expect(screen.getByText('知识库加载失败，请稍后重试')).toBeInTheDocument()
    )
  })
})
