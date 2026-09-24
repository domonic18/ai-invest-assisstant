import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

vi.mock('@/hooks/useAdminKb', () => ({
  useKbSources: vi.fn(),
  useKbSourceMedia: vi.fn(),
  useKbImages: vi.fn(),
  useRedescribeKbImage: vi.fn(),
  usePatchKbImage: vi.fn(),
}))

import {
  useKbImages,
  useKbSourceMedia,
  useKbSources,
  usePatchKbImage,
  useRedescribeKbImage,
} from '@/hooks/useAdminKb'
import type { ApiKbImageListResponse } from '@ai-invest/shared'

import { ImagesTab } from './ImagesTab'

const mockedSources = vi.mocked(useKbSources)
const mockedMedia = vi.mocked(useKbSourceMedia)
const mockedImages = vi.mocked(useKbImages)
const mockedRedescribe = vi.mocked(useRedescribeKbImage)
const mockedPatch = vi.mocked(usePatchKbImage)

const image = {
  id: 8,
  sourceId: 1,
  mediaId: 3,
  pageNo: null,
  startMs: 28_000,
  endMs: null,
  thumbUrl: 'https://signed/thumb.jpg',
  describeStatus: 'done',
  describeAttempts: 0,
  textInImage: 'MA5',
  caption: '支撑线讲解',
  visionDescription: 'K 线支撑位画线',
  indexExcluded: false,
  createdAt: '2026-09-19T00:00:00Z',
} as ApiKbImageListResponse['items'][number]

function mutationStub() {
  return { mutateAsync: vi.fn().mockResolvedValue({}), isPending: false }
}

function setup(listing?: ApiKbImageListResponse) {
  mockedSources.mockReturnValue({
    data: [{ id: 1, name: '课', sourceType: 'course' }],
  } as never)
  mockedMedia.mockReturnValue({
    data: [{ id: 3, mediaKind: 'video', episodeNo: 1, title: '第 1 集' }],
  } as never)
  mockedImages.mockReturnValue({ data: listing, isLoading: false } as never)
  const redo = mutationStub()
  const patch = mutationStub()
  mockedRedescribe.mockReturnValue(redo as never)
  mockedPatch.mockReturnValue(patch as never)
  return { redo: redo.mutateAsync, patch: patch.mutateAsync }
}

async function confirmPopconfirm() {
  const ok = await waitFor(() => {
    const btn = document.querySelector('.ant-popconfirm-buttons .ant-btn-primary')
    if (!btn) throw new Error('popconfirm not open yet')
    return btn
  })
  fireEvent.click(ok)
}

describe('ImagesTab', () => {
  it('renders image card with status tag, timecode and descriptions', () => {
    setup({ items: [image], total: 1 })
    render(<ImagesTab sourceId={1} onSourceChange={vi.fn()} />)
    // 「已描述」同时命中状态 Tag 与状态筛选 Radio.Button
    expect(screen.getAllByText('已描述')).toHaveLength(2)
    expect(screen.getByText('00:28')).toBeInTheDocument()
    expect(screen.getByText('支撑线讲解')).toBeInTheDocument()
    expect(screen.getByText('K 线支撑位画线')).toBeInTheDocument()
    expect(screen.getByText('共 1 张')).toBeInTheDocument()
  })

  it('renders excluded flag with restore action', () => {
    setup({ items: [{ ...image, indexExcluded: true }], total: 1 })
    render(<ImagesTab sourceId={1} onSourceChange={vi.fn()} />)
    expect(screen.getByText('已排除')).toBeInTheDocument()
    expect(screen.getByText('恢复索引')).toBeInTheDocument()
  })

  it('redescribe confirms then calls mutation with image id', async () => {
    const { redo } = setup({ items: [image], total: 1 })
    render(<ImagesTab sourceId={1} onSourceChange={vi.fn()} />)
    fireEvent.click(screen.getByText('重新描述'))
    await confirmPopconfirm()
    await waitFor(() => expect(redo).toHaveBeenCalledWith(8))
  })

  it('exclude confirms then patches indexExcluded true', async () => {
    const { patch } = setup({ items: [image], total: 1 })
    render(<ImagesTab sourceId={1} onSourceChange={vi.fn()} />)
    fireEvent.click(screen.getByText('排除'))
    await confirmPopconfirm()
    await waitFor(() =>
      expect(patch).toHaveBeenCalledWith({ imageId: 8, data: { indexExcluded: true } })
    )
  })

  it('status filter re-queries with selected status', () => {
    setup({ items: [image], total: 1 })
    render(<ImagesTab sourceId={1} onSourceChange={vi.fn()} />)
    fireEvent.click(screen.getByRole('radio', { name: '已描述' }))
    const calls = mockedImages.mock.calls
    expect(calls[calls.length - 1]).toEqual([1, null, 'done', 1, 24])
  })

  it('empty listing shows placeholder', () => {
    setup({ items: [], total: 0 })
    render(<ImagesTab sourceId={1} onSourceChange={vi.fn()} />)
    expect(
      screen.getByText('暂无图片资产（视频选帧由 kb-vision 定时任务生成）')
    ).toBeInTheDocument()
  })

  it('missing source shows guidance', () => {
    setup(undefined)
    render(<ImagesTab sourceId={null} onSourceChange={vi.fn()} />)
    expect(screen.getByText('请先选择知识库')).toBeInTheDocument()
  })
})
