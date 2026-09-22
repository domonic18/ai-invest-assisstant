import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

const closePanel = vi.fn()

vi.mock('@/stores/assistant', () => ({
  useAssistantStore: { getState: () => ({ closePanel }) },
}))

import { KbMediaChips } from './KbMediaChips'

function LocationProbe() {
  const location = useLocation()
  return <div data-testid="location">{location.pathname + location.search}</div>
}

function renderChips(result: unknown) {
  return render(
    <MemoryRouter>
      <KbMediaChips result={result} />
      <LocationProbe />
    </MemoryRouter>
  )
}

describe('KbMediaChips', () => {
  it('renders deduped chips from points and segments', () => {
    // 运行时真实形状：ToolMessage content 是 JSON 字符串
    renderChips(
      JSON.stringify({
        points: [
          {
            title: '均线金叉',
            media: { id: 2, kind: 'video', title: '第3课', episode_no: 3, seek_ms: 330000 },
          },
          {
            title: '同段引用去重',
            media: { id: 2, kind: 'video', title: '第3课', episode_no: 3, seek_ms: 330000 },
          },
          { title: '书引用', media: { id: 5, kind: 'book', title: '缠中说禅', page_no: 45 } },
          { title: '无定位卡片' },
        ],
        segments: [{ media: { id: 2, kind: 'video', episode_no: 3, seek_ms: 600000 } }],
      }),
    )
    const chips = screen.getAllByRole('button')
    expect(chips.map((c) => c.textContent)).toEqual([
      '第3集 05:30',
      '第45页',
      '第3集 10:00',
    ])
  })

  it('chip click closes panel and navigates to /kb playback params', () => {
    renderChips({
      points: [
        { media: { id: 2, kind: 'video', title: '第3课 均线', episode_no: 3, seek_ms: 330000 } },
      ],
      segments: [],
    })
    fireEvent.click(screen.getByRole('button'))
    expect(closePanel).toHaveBeenCalled()
    expect(screen.getByTestId('location').textContent).toBe(
      '/kb?mediaId=2&kind=video&seekMs=330000&title=%E7%AC%AC3%E8%AF%BE+%E5%9D%87%E7%BA%BF&episodeNo=3'
    )
  })

  it('renders nothing without media refs', () => {
    renderChips({ points: [{ title: 'x' }], segments: [] })
    expect(screen.queryAllByRole('button')).toHaveLength(0)
  })
})
