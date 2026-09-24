import { act, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ReactNode } from 'react'

vi.mock('@/api/adminKbMedia', () => ({
  initKbMediaUploads: vi.fn(),
  confirmKbMediaUploaded: vi.fn(),
  putFileToCos: vi.fn(),
  createKbUploadSession: vi.fn(),
  abortKbUploadSession: vi.fn(),
}))

vi.mock('@/utils/fileHash', () => ({
  computeFileMd5: vi.fn(),
}))

vi.mock('@/utils/multipartUpload', () => ({
  uploadMultipartParts: vi.fn(),
  clearStoredSession: vi.fn(),
  KB_MULTIPART_THRESHOLD_BYTES: 64 * 1024 * 1024,
}))

vi.mock('@/utils/mediaMeta', () => ({
  probeMediaDuration: vi.fn(),
}))

import {
  confirmKbMediaUploaded,
  initKbMediaUploads,
  putFileToCos,
} from '@/api/adminKbMedia'
import { computeFileMd5 } from '@/utils/fileHash'
import { probeMediaDuration } from '@/utils/mediaMeta'
import { uploadMultipartParts } from '@/utils/multipartUpload'

import { inferMediaKind, useKbUploadQueue } from './useKbUploadQueue'

const mockedInit = vi.mocked(initKbMediaUploads)
const mockedPut = vi.mocked(putFileToCos)
const mockedConfirm = vi.mocked(confirmKbMediaUploaded)
const mockedHash = vi.mocked(computeFileMd5)
const mockedMultipart = vi.mocked(uploadMultipartParts)
const mockedProbe = vi.mocked(probeMediaDuration)

function makeFile(name: string, size = 100): File {
  const file = new File([new Uint8Array(8).fill(65)], name, { type: 'video/mp4' })
  if (size !== 8) {
    Object.defineProperty(file, 'size', { value: size })
  }
  return file
}

function initItem(
  mediaId: number | null,
  fileName: string,
  uploadUrl: string | null,
  conflictWith: string | null = null
) {
  return { mediaId, fileName, cosKey: uploadUrl ? 'kb/1/x' : null, uploadUrl, conflictWith }
}

beforeEach(() => {
  vi.clearAllMocks()
  mockedHash.mockResolvedValue('a'.repeat(32))
  mockedPut.mockResolvedValue(undefined)
  mockedConfirm.mockResolvedValue({} as never)
  mockedProbe.mockResolvedValue(600)
})

describe('inferMediaKind', () => {
  it('maps extensions to media kinds', () => {
    expect(inferMediaKind('第1集.MP4')).toBe('video')
    expect(inferMediaKind('lecture.m4a')).toBe('audio')
    expect(inferMediaKind('book.epub')).toBe('book')
    expect(inferMediaKind('notes.txt')).toBeNull()
    expect(inferMediaKind('noext')).toBeNull()
  })
})

describe('useKbUploadQueue', () => {
  function renderQueueHook(sourceId: number | null = 1) {
    const queryClient = new QueryClient()
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )
    return renderHook(() => useKbUploadQueue(sourceId), { wrapper })
  }

  it('runs hash → init → put → confirm and finishes done', async () => {
    mockedInit.mockResolvedValue({
      items: [initItem(5, 'e1.mp4', 'https://cos/put')],
    })
    const { result } = renderQueueHook()

    act(() => {
      result.current.start([makeFile('e1.mp4')])
    })

    await waitFor(() => {
      expect(result.current.items[0]?.status).toBe('done')
    })

    expect(mockedHash).toHaveBeenCalledTimes(1)
    expect(mockedInit).toHaveBeenCalledWith(1, {
      items: [
        expect.objectContaining({
          fileName: 'e1.mp4',
          relativePath: 'e1.mp4',
          size: 100,
          hash: 'a'.repeat(32),
          mediaKind: 'video',
          durationSeconds: 600,
        }),
      ],
    })
    expect(mockedPut).toHaveBeenCalledWith('https://cos/put', expect.any(File), expect.any(Function))
    expect(mockedConfirm).toHaveBeenCalledWith(5)
    expect(result.current.items[0]?.mediaId).toBe(5)
    expect(result.current.progress[result.current.items[0].uid]).toBe(100)
    expect(result.current.running).toBe(false)
  })

  it('runs uploads with at most 3 concurrent lanes', async () => {
    mockedHash.mockImplementation((file) =>
      Promise.resolve(file.name.repeat(32).slice(0, 32))
    )
    const resolvers: Array<() => void> = []
    let concurrent = 0
    let maxConcurrent = 0
    mockedPut.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          concurrent++
          maxConcurrent = Math.max(maxConcurrent, concurrent)
          resolvers.push(() => {
            concurrent--
            resolve()
          })
        })
    )
    const { result } = renderQueueHook()

    act(() => {
      result.current.start(
        ['e1.mp4', 'e2.mp4', 'e3.mp4', 'e4.mp4', 'e5.mp4'].map((n) => makeFile(n))
      )
    })

    await waitFor(() => {
      expect(mockedPut).toHaveBeenCalledTimes(3)
    })
    expect(maxConcurrent).toBe(3)

    // 后续文件接力占用 lane，循环放行直至队列排空
    await waitFor(() => {
      while (resolvers.length) resolvers.shift()!()
      expect(result.current.running).toBe(false)
    })
    expect(result.current.items.every((it) => it.status === 'done')).toBe(true)
    expect(mockedPut).toHaveBeenCalledTimes(5)
  })

  it('skips later in-batch duplicates and uploads only the first copy', async () => {
    const { result } = renderQueueHook()

    act(() => {
      result.current.start([makeFile('总论1.mp4'), makeFile('总论2.mp4')])
    })

    await waitFor(() => {
      expect(result.current.running).toBe(false)
    })

    expect(mockedInit).toHaveBeenCalledTimes(1)
    expect(mockedInit).toHaveBeenCalledWith(1, {
      items: [expect.objectContaining({ fileName: '总论1.mp4' })],
    })
    expect(mockedPut).toHaveBeenCalledTimes(1)
    expect(result.current.items[0].status).toBe('done')
    expect(result.current.items[1].status).toBe('skipped')
    expect(result.current.items[1].error).toContain('与批内「总论1.mp4」内容相同')
  })

  it('skips server-reported existing conflicts and uploads the rest', async () => {
    mockedHash.mockImplementation((file) =>
      Promise.resolve(file.name === 'e1.mp4' ? 'a'.repeat(32) : 'b'.repeat(32))
    )
    mockedInit.mockImplementation((_, data) =>
      Promise.resolve({
        items: [
          [
            initItem(null, 'e1.mp4', null, '已有素材「e1」（第 1 集）'),
            initItem(2, 'e2.mp4', 'https://cos/2'),
          ][data.items[0].fileName === 'e1.mp4' ? 0 : 1],
        ],
      })
    )
    const { result } = renderQueueHook()

    act(() => {
      result.current.start([makeFile('e1.mp4'), makeFile('e2.mp4')])
    })

    await waitFor(() => {
      expect(result.current.running).toBe(false)
    })

    expect(result.current.items[0].status).toBe('skipped')
    expect(result.current.items[0].error).toContain('已有素材「e1」（第 1 集）')
    expect(result.current.items[1].status).toBe('done')
    expect(mockedPut).toHaveBeenCalledTimes(1)
    expect(mockedConfirm).toHaveBeenCalledTimes(1)
    expect(mockedConfirm).toHaveBeenCalledWith(2)
  })

  it('marks items failed when init rejects (structural 409)', async () => {
    mockedHash.mockImplementation((file) =>
      Promise.resolve(file.name === 'e1.mp4' ? 'a'.repeat(32) : 'b'.repeat(32))
    )
    mockedInit.mockRejectedValue(new Error('该知识库已存在相同内容的素材'))
    const { result } = renderQueueHook()

    act(() => {
      result.current.start([makeFile('e1.mp4'), makeFile('e2.mp4')])
    })

    await waitFor(() => {
      expect(result.current.running).toBe(false)
    })

    expect(result.current.items).toHaveLength(2)
    for (const item of result.current.items) {
      expect(item.status).toBe('failed')
      expect(item.error).toContain('相同内容')
    }
    expect(mockedPut).not.toHaveBeenCalled()
    expect(mockedConfirm).not.toHaveBeenCalled()
  })

  it('keeps other files going when one PUT fails mid-queue', async () => {
    mockedHash.mockImplementation((file) =>
      Promise.resolve(file.name === 'e1.mp4' ? 'a'.repeat(32) : 'b'.repeat(32))
    )
    mockedInit.mockImplementation((_, data) =>
      Promise.resolve({
        items: [
          [initItem(1, 'e1.mp4', 'https://cos/1'), initItem(2, 'e2.mp4', 'https://cos/2')][
            data.items[0].fileName === 'e1.mp4' ? 0 : 1
          ],
        ],
      })
    )
    mockedPut.mockRejectedValueOnce(new Error('网络中断'))
    const { result } = renderQueueHook()

    act(() => {
      result.current.start([makeFile('e1.mp4'), makeFile('e2.mp4')])
    })

    await waitFor(() => {
      expect(result.current.running).toBe(false)
    })

    expect(result.current.items[0].status).toBe('failed')
    expect(result.current.items[0].error).toBe('网络中断')
    expect(result.current.items[1].status).toBe('done')
    expect(mockedConfirm).toHaveBeenCalledTimes(1)
    expect(mockedConfirm).toHaveBeenCalledWith(2)
  })

  it('routes large files through multipart sessions instead of single PUT', async () => {
    mockedInit.mockResolvedValue({
      items: [initItem(7, 'big.mp4', 'https://cos/put')],
    })
    const { result } = renderQueueHook()

    act(() => {
      result.current.start([makeFile('big.mp4', 200 * 1024 * 1024)])
    })

    await waitFor(() => {
      expect(result.current.items[0]?.status).toBe('done')
    })

    expect(mockedMultipart).toHaveBeenCalledWith(
      expect.objectContaining({
        file: expect.any(File),
        hash: 'a'.repeat(32),
        mediaId: 7,
      })
    )
    expect(mockedPut).not.toHaveBeenCalled()
    expect(mockedConfirm).toHaveBeenCalledWith(7)
  })

  it('retries a failed file with a fresh init and completes', async () => {
    mockedInit.mockResolvedValue({
      items: [initItem(5, 'e1.mp4', 'https://cos/put')],
    })
    mockedPut.mockRejectedValueOnce(new Error('网络中断'))
    const { result } = renderQueueHook()

    act(() => {
      result.current.start([makeFile('e1.mp4')])
    })

    await waitFor(() => {
      expect(result.current.items[0]?.status).toBe('failed')
    })

    act(() => {
      void result.current.retry(result.current.items[0].uid)
    })

    await waitFor(() => {
      expect(result.current.items[0]?.status).toBe('done')
    })

    expect(mockedInit).toHaveBeenCalledTimes(2)
    expect(mockedPut).toHaveBeenCalledTimes(2)
    expect(mockedConfirm).toHaveBeenCalledTimes(1)
    expect(result.current.items[0].error).toBeNull()
  })

  it('maps Network Error on PUT to a friendly hint', async () => {
    mockedInit.mockResolvedValue({
      items: [initItem(5, 'e1.mp4', 'https://cos/put')],
    })
    mockedPut.mockRejectedValue(new Error('Network Error'))
    const { result } = renderQueueHook()

    act(() => {
      result.current.start([makeFile('e1.mp4')])
    })

    await waitFor(() => {
      expect(result.current.running).toBe(false)
    })

    expect(result.current.items[0].status).toBe('failed')
    expect(result.current.items[0].error).toContain('MINIO_PUBLIC_ENDPOINT')
  })

  it('ignores unsupported files and requires a source', () => {
    const { result } = renderQueueHook()
    expect(result.current.start([makeFile('notes.txt')])).toBe(0)

    const { result: noSource } = renderQueueHook(null)
    expect(noSource.current.start([makeFile('e1.mp4')])).toBe(0)
    expect(mockedInit).not.toHaveBeenCalled()
  })
})
