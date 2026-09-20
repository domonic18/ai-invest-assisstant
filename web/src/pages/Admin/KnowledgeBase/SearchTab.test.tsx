import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

vi.mock('@/hooks/useAdminKb', () => ({
  useKbSources: vi.fn(),
}))

vi.mock('@/hooks/useKbSearch', () => ({
  useKbSearch: vi.fn(),
  useKbPublishedChapters: vi.fn(),
}))

import { useKbSources } from '@/hooks/useAdminKb'
import { useKbPublishedChapters, useKbSearch } from '@/hooks/useKbSearch'
import type { ApiKbSearchResponse } from '@ai-invest/shared'

import { SearchTab } from './SearchTab'

const mockedSources = vi.mocked(useKbSources)
const mockedChapters = vi.mocked(useKbPublishedChapters)
const mockedSearch = vi.mocked(useKbSearch)

const point = {
  id: 1,
  sourceId: 1,
  mediaId: 3,
  mediaKind: 'video',
  episodeNo: 3,
  mediaTitle: '均线入门课',
  pointType: 'case',
  title: '支撑线回踩买入',
  body: '支撑线回踩不破且缩量企稳时可考虑分批买入',
  termDefinition: '支撑线：多次回踩不破的低点连线',
  applicableScene: null,
  excerpt: '我们看这条支撑线，回踩三次都没有破',
  chapterPath: ['第一章', '形态'],
  relatedIds: [],
  startMs: 10_000,
  endMs: 40_000,
  pageStart: null,
  pageEnd: null,
  score: 0.032787,
  frames: [
    { id: 9, startMs: 15_000, thumbUrl: 'https://signed/frame.jpg', caption: '支撑线画法' },
  ],
} as ApiKbSearchResponse['points'][number]

const segment = {
  id: 5,
  sourceId: 1,
  mediaId: 3,
  mediaKind: 'video',
  episodeNo: 2,
  mediaTitle: '形态专题',
  text: '这一段我们讲解支撑线的具体画法',
  startMs: 9_000,
  endMs: 14_000,
  seekMs: 5_000,
  score: 0.016394,
} as ApiKbSearchResponse['segments'][number]

const image = {
  id: 8,
  sourceId: 1,
  mediaId: 4,
  mediaKind: 'book',
  episodeNo: null,
  pageNo: 8,
  startMs: null,
  textInImage: 'MA5',
  caption: '头肩顶图示',
  thumbUrl: 'https://signed/image.jpg',
  score: 0.016129,
} as ApiKbSearchResponse['images'][number]

const fullResult: ApiKbSearchResponse = {
  query: '支撑线',
  degraded: null,
  points: [point],
  segments: [segment],
  images: [image],
}

function setup(result?: ApiKbSearchResponse) {
  let current = result
  mockedSources.mockReturnValue({
    data: [{ id: 1, name: '课', sourceType: 'course' }],
  } as never)
  mockedChapters.mockReturnValue({
    data: {
      chapters: [
        { id: '1', title: '第一章', children: [{ id: '1.1', title: '形态', children: [] }] },
      ],
    },
  } as never)
  mockedSearch.mockImplementation(() => ({ data: current, isLoading: false }) as never)
  return {
    swap(next: ApiKbSearchResponse) {
      current = next
    },
  }
}

function submitQuery() {
  fireEvent.change(screen.getByPlaceholderText('搜索知识点 / 原文 / 图片描述'), {
    target: { value: '支撑线' },
  })
  fireEvent.click(screen.getByText('检索'))
}

function lastSubmitted() {
  const calls = mockedSearch.mock.calls
  return calls[calls.length - 1][0]
}

describe('SearchTab', () => {
  it('renders chapter tree, three hit sections and term highlights', async () => {
    setup(fullResult)
    const { container } = render(<SearchTab sourceId={1} onSourceChange={vi.fn()} />)

    expect(screen.getByText('第一章')).toBeInTheDocument()
    expect(screen.getByText('形态')).toBeInTheDocument()

    submitQuery()
    await waitFor(() => expect(screen.getByText('头肩顶图示')).toBeInTheDocument())

    expect(lastSubmitted()).toEqual({
      q: '支撑线',
      sourceId: 1,
      chapterPath: [],
      kind: null,
    })
    expect(screen.getByText('案例')).toBeInTheDocument()
    // 标题被 mark 拆分为多节点，按子串断言
    expect(screen.getByText('回踩买入', { exact: false })).toBeInTheDocument()
    expect(screen.getByText('多次回踩不破的低点连线', { exact: false })).toBeInTheDocument()
    expect(screen.getByText('RRF 0.0328')).toBeInTheDocument()
    expect(screen.getByText('第 3 集 00:10–00:40 · 均线入门课')).toBeInTheDocument()
    expect(screen.getByAltText('支撑线画法')).toBeInTheDocument()
    expect(screen.getByText('第 2 集 00:09–00:14 · 形态专题')).toBeInTheDocument()
    expect(screen.getByText('第 8 页')).toBeInTheDocument()
    expect(container.querySelectorAll('mark').length).toBeGreaterThan(0)
  })

  it('kind segmented filter re-submits with kind', async () => {
    setup(fullResult)
    render(<SearchTab sourceId={1} onSourceChange={vi.fn()} />)
    submitQuery()
    await waitFor(() => expect(screen.getByText('头肩顶图示')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('radio', { name: '卡片' }))
    await waitFor(() => expect(lastSubmitted()?.kind).toBe('point'))
    expect(screen.queryByText('头肩顶图示')).not.toBeInTheDocument()
  })

  it('chapter tree selection re-submits with chapter path', async () => {
    setup(fullResult)
    render(<SearchTab sourceId={1} onSourceChange={vi.fn()} />)
    submitQuery()
    await waitFor(() =>
      expect(screen.getByText('回踩买入', { exact: false })).toBeInTheDocument()
    )

    fireEvent.click(screen.getByText('形态'))
    await waitFor(() =>
      expect(lastSubmitted()?.chapterPath).toEqual(['第一章', '形态'])
    )
    // 卡片章节路径 + 已选章节 Tag 各一处
    expect(screen.getAllByText('第一章 / 形态')).toHaveLength(2)
  })

  it('degraded alerts explain unavailability', async () => {
    const { swap } = setup({ ...fullResult, degraded: 'es_unavailable' })
    render(<SearchTab sourceId={1} onSourceChange={vi.fn()} />)
    submitQuery()
    await waitFor(() =>
      expect(screen.getByText('检索服务暂不可用，请稍后再试')).toBeInTheDocument()
    )

    swap({ ...fullResult, degraded: 'embedding_unavailable' })
    submitQuery()
    await waitFor(() =>
      expect(screen.getByText('向量通道暂不可用，已降级为关键词检索')).toBeInTheDocument()
    )
  })

  it('empty result shows miss message', async () => {
    setup({ query: '支撑线', degraded: null, points: [], segments: [], images: [] })
    render(<SearchTab sourceId={1} onSourceChange={vi.fn()} />)
    submitQuery()
    await waitFor(() =>
      expect(screen.getByText('「支撑线」未找到命中')).toBeInTheDocument()
    )
  })

  it('idle state shows guidance placeholder', () => {
    setup(undefined)
    render(<SearchTab sourceId={1} onSourceChange={vi.fn()} />)
    expect(
      screen.getByText('输入关键词开始混合检索（BM25 + 向量双路召回）')
    ).toBeInTheDocument()
  })
})
