import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const sendQuestion = vi.fn()

vi.mock('@/api/kb', () => ({
  fetchKbPlaybackToken: vi.fn(),
}))

vi.mock('@/pages/Admin/KnowledgeBase/KnowledgePlayer', () => ({
  KnowledgePlayer: (props: {
    mediaId: number
    mediaKind: string
    initialSeekMs: number | null
  }) => (
    <div
      data-testid="player-stub"
      data-media={props.mediaId}
      data-kind={props.mediaKind}
      data-seek={props.initialSeekMs ?? 'null'}
    />
  ),
}))

vi.mock('@/pages/Admin/KnowledgeBase/BookReader', () => ({
  BookReader: (props: { mediaId: number; initialPageNo: number | null }) => (
    <div
      data-testid="reader-stub"
      data-media={props.mediaId}
      data-page={props.initialPageNo ?? 'null'}
    />
  ),
}))

vi.mock('@/stores/assistant', () => ({
  useAssistantStore: {
    getState: () => ({ sendQuestion }),
  },
}))

import { fetchKbPlaybackToken } from '@/api/kb'

import { KnowledgeSearchPage } from './index'

const mockedToken = vi.mocked(fetchKbPlaybackToken)

function renderPage(route = '/kb') {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <KnowledgeSearchPage />
    </MemoryRouter>
  )
}

describe('KnowledgeSearchPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('search submit and suggestion chip trigger assistant kb question', () => {
    renderPage()
    fireEvent.change(screen.getByPlaceholderText(/输入知识点/), {
      target: { value: '均线金叉' },
    })
    fireEvent.click(screen.getByRole('button', { name: /搜\s*索/ }))
    fireEvent.click(screen.getByText('止损与仓位管理方法'))
    expect(sendQuestion).toHaveBeenCalledWith('请在知识库中检索并回答：均线金叉')
    expect(sendQuestion).toHaveBeenCalledWith(
      '请在知识库中检索并回答：止损与仓位管理方法'
    )
  })

  it('?mediaId= opens playback modal with player on allowed token', async () => {
    mockedToken.mockResolvedValue({
      token: 't',
      expiresIn: 1800,
      mediaId: 3,
      streamUrl: 'https://minio.local/signed',
      prevMediaId: null,
      nextMediaId: null,
      pageCount: null,
    })
    renderPage('/kb?mediaId=3&kind=video&seekMs=330000&episodeNo=3&title=均线课')

    const player = await screen.findByTestId('player-stub')
    expect(player).toHaveAttribute('data-media', '3')
    expect(player).toHaveAttribute('data-seek', '330000')
    expect(mockedToken).toHaveBeenCalledWith(3)
  })

  it('?kind=book mounts reader at initial page', async () => {
    mockedToken.mockResolvedValue({
      token: 't',
      expiresIn: 1800,
      mediaId: 5,
      streamUrl: null,
      prevMediaId: null,
      nextMediaId: null,
      pageCount: 120,
    })
    renderPage('/kb?mediaId=5&kind=book&pageNo=45')

    const reader = await screen.findByTestId('reader-stub')
    expect(reader).toHaveAttribute('data-media', '5')
    expect(reader).toHaveAttribute('data-page', '45')
  })

  it('403 token renders authorization guidance instead of player', async () => {
    mockedToken.mockRejectedValue({ response: { status: 403 } })
    renderPage('/kb?mediaId=3')

    await waitFor(() =>
      expect(screen.getByText('暂无知识库播放权限')).toBeInTheDocument()
    )
    expect(screen.queryByTestId('player-stub')).not.toBeInTheDocument()
  })

  it('no mediaId renders only the search entry', () => {
    renderPage()
    expect(screen.getByText('知识库')).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
