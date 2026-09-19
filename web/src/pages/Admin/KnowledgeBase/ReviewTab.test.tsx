import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

vi.mock('@/hooks/useAdminKb', () => ({
  useKbSources: vi.fn(),
  useKbChapters: vi.fn(),
  useKbReviewPoints: vi.fn(),
  usePublishKbChapters: vi.fn(),
  useCreateKbPoint: vi.fn(),
  usePatchKbPoint: vi.fn(),
  useApproveKbPoint: vi.fn(),
  useRejectKbPoint: vi.fn(),
  useMergeKbPoints: vi.fn(),
}))

import {
  useApproveKbPoint,
  useCreateKbPoint,
  useKbChapters,
  useKbReviewPoints,
  useKbSources,
  useMergeKbPoints,
  usePatchKbPoint,
  usePublishKbChapters,
  useRejectKbPoint,
} from '@/hooks/useAdminKb'
import type { ApiKbPointListResponse } from '@ai-invest/shared'

import { ReviewTab } from './ReviewTab'

const mockedApprove = vi.mocked(useApproveKbPoint)
const mockedPatch = vi.mocked(usePatchKbPoint)
const mockedReject = vi.mocked(useRejectKbPoint)
const mockedMerge = vi.mocked(useMergeKbPoints)
const mockedPublish = vi.mocked(usePublishKbChapters)
const mockedChapters = vi.mocked(useKbChapters)
const mockedPoints = vi.mocked(useKbReviewPoints)
const mockedSources = vi.mocked(useKbSources)
const mockedCreate = vi.mocked(useCreateKbPoint)

const point = {
  id: 5,
  sourceId: 1,
  mediaId: 3,
  episodeNo: 7,
  mediaTitle: '第 7 集',
  pointType: 'concept',
  title: '复利',
  body: '正文内容',
  termDefinition: null,
  applicableScene: null,
  excerpt: '摘抄',
  startMs: 2_535_000,
  endMs: 2_642_000,
  pageStart: null,
  pageEnd: null,
  relatedIds: [],
  chapterPath: ['价值篇'],
  status: 'draft',
  needsReview: false,
  reviewNote: null,
  reviewedAt: null,
  createdAt: '2026-09-19T00:00:00Z',
  updatedAt: '2026-09-19T00:00:00Z',
} as ApiKbPointListResponse['items'][number]

const listing: ApiKbPointListResponse = {
  items: [point, { ...point, id: 6, title: '安全边际', needsReview: true }],
  total: 2,
  counts: { draft: 2, published: 3, rejected: 1, needsReview: 1 },
}

function mutationStub() {
  return { mutateAsync: vi.fn().mockResolvedValue({}), isPending: false }
}

function setup(points: ApiKbPointListResponse | undefined) {
  mockedSources.mockReturnValue({ data: [{ id: 1, name: '课', sourceType: 'course' }] } as never)
  mockedCreate.mockReturnValue(mutationStub() as never)
  mockedPoints.mockReturnValue({ data: points, isLoading: false } as never)
  mockedChapters.mockReturnValue({
    data: {
      draft: [{ id: '1', title: '价值篇', children: [{ id: '1.1', title: '复利', children: [] }] }],
      published: null,
    },
  } as never)
  mockedPublish.mockReturnValue(mutationStub() as never)
  const approveMock = mutationStub()
  const patchMock = mutationStub()
  mockedApprove.mockReturnValue(approveMock as never)
  mockedPatch.mockReturnValue(patchMock as never)
  mockedReject.mockReturnValue(mutationStub() as never)
  mockedMerge.mockReturnValue(mutationStub() as never)
  return { approveMock: approveMock.mutateAsync, patchMock: patchMock.mutateAsync }
}

describe('ReviewTab', () => {
  it('renders status chips with counts', () => {
    setup(listing)
    render(<ReviewTab sourceId={1} onSourceChange={vi.fn()} />)
    expect(screen.getByText(/待审核 \(2\)/)).toBeInTheDocument()
    expect(screen.getByText(/已通过 \(3\)/)).toBeInTheDocument()
    expect(screen.getByText(/已驳回 \(1\)/)).toBeInTheDocument()
  })

  it('renders point cards with footer and review flag', () => {
    setup(listing)
    render(<ReviewTab sourceId={1} onSourceChange={vi.fn()} />)
    expect(screen.getAllByTestId('point-card')).toHaveLength(2)
    // 原文脚注：媒体标题 + 毫秒时间码格式化（文本跨 JSX 节点拆分，按容器匹配）
    const footers = screen.getAllByText((_, el) => el?.textContent === '原文 · 第 7 集 42:15–44:02 · 价值篇')
    expect(footers).toHaveLength(2)
    expect(screen.getByText('需人工复核')).toBeInTheDocument()
  })

  it('approve calls mutation', async () => {
    const { approveMock } = setup(listing)
    render(<ReviewTab sourceId={1} onSourceChange={vi.fn()} />)
    fireEvent.click(screen.getAllByText('通过')[0])
    await waitFor(() => expect(approveMock).toHaveBeenCalledWith(5))
  })

  it('patch-approve patches then approves in order', async () => {
    const { approveMock, patchMock } = setup(listing)
    render(<ReviewTab sourceId={1} onSourceChange={vi.fn()} />)
    fireEvent.click(screen.getAllByText('修订后通过')[0])
    fireEvent.click(screen.getByText('保存并通过'))
    await waitFor(() => {
      expect(patchMock).toHaveBeenCalled()
      expect(approveMock).toHaveBeenCalledWith(5)
    })
    expect(patchMock.mock.invocationCallOrder[0]).toBeLessThan(
      approveMock.mock.invocationCallOrder[0]
    )
  })

  it('empty queue shows placeholder', () => {
    setup({ items: [], total: 0, counts: { draft: 0, published: 0, rejected: 0, needsReview: 0 } })
    render(<ReviewTab sourceId={1} onSourceChange={vi.fn()} />)
    expect(screen.getByText('暂无待审核草稿。')).toBeInTheDocument()
  })
})
