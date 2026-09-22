import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

vi.mock('@/hooks/useAdminKb', () => ({
  useKbSources: vi.fn(),
}))

vi.mock('@/hooks/useKbSearch', () => ({
  useKbSearch: vi.fn(),
  useKbPublishedChapters: vi.fn(),
}))

vi.mock('@/api/kb', () => ({
  fetchKbImageOriginalUrl: vi.fn(),
}))

vi.mock('./KnowledgePlayer', () => ({
  KnowledgePlayer: (props: {
    mediaId: number
    mediaKind: string
    title: string | null
    initialSeekMs: number | null
    hitIntervals: { startMs: number; endMs: number; label?: string }[]
  }) => (
    <div
      data-testid="player-stub"
      data-media={props.mediaId}
      data-kind={props.mediaKind}
      data-title={props.title ?? ''}
      data-seek={props.initialSeekMs ?? 'null'}
      data-intervals={JSON.stringify(props.hitIntervals)}
    />
  ),
}))

vi.mock('./BookReader', () => ({
  BookReader: (props: {
    mediaId: number
    initialPageNo: number | null
    hitPages: { pageNo: number; label?: string }[]
  }) => (
    <div
      data-testid="reader-stub"
      data-media={props.mediaId}
      data-page={props.initialPageNo ?? 'null'}
      data-pages={JSON.stringify(props.hitPages)}
    />
  ),
}))

import { fetchKbImageOriginalUrl } from '@/api/kb'
import { useKbSources } from '@/hooks/useAdminKb'
import { useKbPublishedChapters, useKbSearch } from '@/hooks/useKbSearch'
import type { ApiKbSearchResponse } from '@ai-invest/shared'

import { SearchTab } from './SearchTab'

const mockedSources = vi.mocked(useKbSources)
const mockedChapters = vi.mocked(useKbPublishedChapters)
const mockedSearch = vi.mocked(useKbSearch)
const mockedOriginalUrl = vi.mocked(fetchKbImageOriginalUrl)

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

const bookPoint = {
  ...point,
  id: 2,
  mediaId: 4,
  mediaKind: 'book',
  episodeNo: null,
  mediaTitle: '蜡烛图技术',
  pointType: 'concept',
  title: '头肩顶形态',
  startMs: null,
  endMs: null,
  pageStart: 42,
  pageEnd: 43,
  frames: [],
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

const bookResult: ApiKbSearchResponse = {
  query: '头肩顶',
  degraded: null,
  points: [bookPoint],
  segments: [],
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

  it('degraded alert explains embedding fallback', async () => {
    setup({ ...fullResult, degraded: 'embedding_unavailable' })
    render(<SearchTab sourceId={1} onSourceChange={vi.fn()} />)
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
      screen.getByText('输入关键词开始混合检索（关键词 + 向量双路召回）')
    ).toBeInTheDocument()
  })

  it('point locate launches player with pre-roll seek and merged hit intervals', async () => {
    setup(fullResult)
    render(<SearchTab sourceId={1} onSourceChange={vi.fn()} />)
    submitQuery()
    await waitFor(() => expect(screen.getByText('播放定位')).toBeInTheDocument())

    fireEvent.click(screen.getAllByText('播放定位')[0])

    const stub = screen.getByTestId('player-stub')
    expect(stub.dataset.media).toBe('3')
    expect(stub.dataset.kind).toBe('video')
    expect(stub.dataset.title).toBe('均线入门课')
    // 卡片前滚 4s（10000 − 4000）
    expect(stub.dataset.seek).toBe('6000')
    // 原文分段在前（9000）+ 卡片区间（10000–40000）
    expect(JSON.parse(stub.dataset.intervals ?? '[]')).toEqual([
      { startMs: 9000, endMs: 14000, label: undefined },
      { startMs: 10000, endMs: 40000, label: '支撑线回踩买入' },
    ])
  })

  it('segment locate launches player at server seekMs', async () => {
    setup(fullResult)
    render(<SearchTab sourceId={1} onSourceChange={vi.fn()} />)
    submitQuery()
    await waitFor(() => expect(screen.getByText('播放片段')).toBeInTheDocument())

    fireEvent.click(screen.getByText('播放片段'))

    const stub = screen.getByTestId('player-stub')
    expect(stub.dataset.media).toBe('3')
    expect(stub.dataset.seek).toBe('5000')
  })

  it('book locate launches reader with initial page and hit pages', async () => {
    setup(bookResult)
    render(<SearchTab sourceId={1} onSourceChange={vi.fn()} />)
    submitQuery()
    await waitFor(() => expect(screen.getByText('阅读定位')).toBeInTheDocument())

    fireEvent.click(screen.getByText('阅读定位'))

    const stub = screen.getByTestId('reader-stub')
    expect(stub.dataset.media).toBe('4')
    expect(stub.dataset.page).toBe('42')
    // 书嵌图 pageNo 8 + 卡片 pageStart 42（按页码排序）
    expect(JSON.parse(stub.dataset.pages ?? '[]')).toEqual([
      { pageNo: 8, label: undefined },
      { pageNo: 42, label: '头肩顶形态' },
    ])
  })

  it('image original opens presigned modal', async () => {
    setup(bookResult)
    mockedOriginalUrl.mockResolvedValue({ url: 'https://signed/original.png', expiresIn: 900 })
    render(<SearchTab sourceId={1} onSourceChange={vi.fn()} />)
    submitQuery()
    await waitFor(() => expect(screen.getByText('原图')).toBeInTheDocument())

    fireEvent.click(screen.getByText('原图'))

    expect(mockedOriginalUrl).toHaveBeenCalledWith(8)
    const dialog = await screen.findByRole('dialog')
    expect(
      within(dialog).getByAltText('头肩顶图示')
    ).toHaveAttribute('src', 'https://signed/original.png')
  })
})
