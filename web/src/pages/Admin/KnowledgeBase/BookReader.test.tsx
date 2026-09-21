import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/kb', () => ({
  fetchKbPlaybackToken: vi.fn(),
  kbBookPageUrl: vi.fn(
    (mediaId: number, page: number, token: string) => `/kb/media/${mediaId}/book/${page}?t=${token}`
  ),
}))

import { fetchKbPlaybackToken } from '@/api/kb'

import { BookReader } from './BookReader'

const mockedToken = vi.mocked(fetchKbPlaybackToken)

async function renderReader(props: Parameters<typeof BookReader>[0]) {
  const utils = render(<BookReader {...props} />)
  const img = await waitFor(() => {
    const el = utils.container.querySelector('img')
    expect(el).not.toBeNull()
    return el as HTMLImageElement
  })
  fireEvent.load(img)
  return { ...utils, img }
}

describe('BookReader', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    mockedToken.mockResolvedValue({
      token: 'read-tok',
      expiresIn: 1800,
      mediaId: 7,
      prevMediaId: null,
      nextMediaId: null,
      pageCount: 120,
    })
  })

  it('loads token and renders watermarked page bitmap with resume persistence', async () => {
    const { img } = await renderReader({ mediaId: 7, title: '蜡烛图技术' })

    expect(mockedToken).toHaveBeenCalledWith(7)
    expect(img.getAttribute('src')).toBe('/kb/media/7/book/1?t=read-tok')
    expect(img.getAttribute('draggable')).toBe('false')
    expect(screen.getByText('蜡烛图技术')).toBeInTheDocument()
    expect(screen.getByText('第 1 / 120 页')).toBeInTheDocument()
    expect(localStorage.getItem('kb-reader-page:7')).toBe('1')
  })

  it('initialPageNo wins over saved position and shows hit badge on hit pages', async () => {
    localStorage.setItem('kb-reader-page:7', '55')
    const { img } = await renderReader({
      mediaId: 7,
      initialPageNo: 42,
      hitPages: [
        { pageNo: 42, label: '头肩顶形态' },
        { pageNo: 88 },
      ],
    })

    expect(screen.getByText('第 42 / 120 页')).toBeInTheDocument()
    expect(img.getAttribute('src')).toContain('/book/42?')
    // 页角命中标注 + 快捷跳转 chips
    expect(screen.getByText('命中 · 头肩顶形态')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '第 42 页' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '第 88 页' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '第 88 页' }))
    await waitFor(() => expect(screen.getByText('第 88 / 120 页')).toBeInTheDocument())
  })

  it('resumes from saved page when no initialPageNo given', async () => {
    localStorage.setItem('kb-reader-page:7', '31')
    await renderReader({ mediaId: 7 })

    expect(screen.getByText('第 31 / 120 页')).toBeInTheDocument()
  })

  it('prev/next navigate and clamp at page boundaries', async () => {
    await renderReader({ mediaId: 7, initialPageNo: 1 })

    // antd 图标带 aria-label（left/right），按子串匹配可访问名
    expect(screen.getByRole('button', { name: /上一页/ })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: /下一页/ }))
    await waitFor(() => expect(screen.getByText('第 2 / 120 页')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /上一页/ }))
    await waitFor(() => expect(screen.getByText('第 1 / 120 页')).toBeInTheDocument())
  })

  it('arrow keys navigate pages', async () => {
    const { container } = await renderReader({ mediaId: 7 })
    const focusable = container.firstChild as HTMLElement
    focusable.focus()

    fireEvent.keyDown(focusable, { key: 'ArrowRight' })
    await waitFor(() => expect(screen.getByText('第 2 / 120 页')).toBeInTheDocument())
    fireEvent.keyDown(focusable, { key: 'ArrowLeft' })
    await waitFor(() => expect(screen.getByText('第 1 / 120 页')).toBeInTheDocument())
  })
})
