import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/adminKb', () => ({
  initKbMediaUploads: vi.fn(),
  confirmKbMediaUploaded: vi.fn(),
  putFileToCos: vi.fn(),
}))

vi.mock('@/utils/fileHash', () => ({
  computeFileMd5: vi.fn(),
}))

import {
  confirmKbMediaUploaded,
  initKbMediaUploads,
  putFileToCos,
} from '@/api/adminKb'
import { computeFileMd5 } from '@/utils/fileHash'

import { inferMediaKind, useKbUploadQueue } from './useKbUploadQueue'

const mockedInit = vi.mocked(initKbMediaUploads)
const mockedPut = vi.mocked(putFileToCos)
const mockedConfirm = vi.mocked(confirmKbMediaUploaded)
const mockedHash = vi.mocked(computeFileMd5)

function makeFile(name: string, size = 100): File {
  return new File([new Uint8Array(size).fill(65)], name, { type: 'video/mp4' })
}

beforeEach(() => {
  vi.clearAllMocks()
  mockedHash.mockResolvedValue('a'.repeat(32))
  mockedPut.mockResolvedValue(undefined)
  mockedConfirm.mockResolvedValue({} as never)
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
  it('runs hash → init → put → confirm and finishes done', async () => {
    mockedInit.mockResolvedValue({
      items: [
        { mediaId: 5, fileName: 'e1.mp4', cosKey: 'kb/1/5/e1.mp4', uploadUrl: 'https://cos/put' },
      ],
    })
    const { result } = renderHook(() => useKbUploadQueue(1))

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
        }),
      ],
    })
    expect(mockedPut).toHaveBeenCalledWith('https://cos/put', expect.any(File), expect.any(Function))
    expect(mockedConfirm).toHaveBeenCalledWith(5)
    expect(result.current.items[0]?.mediaId).toBe(5)
    expect(result.current.progress[result.current.items[0].uid]).toBe(100)
    expect(result.current.running).toBe(false)
  })

  it('marks all items failed when init rejects (hash conflict 409)', async () => {
    mockedInit.mockRejectedValue(new Error('该知识库已存在相同内容的素材'))
    const { result } = renderHook(() => useKbUploadQueue(1))

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
    mockedInit.mockResolvedValue({
      items: [
        { mediaId: 1, fileName: 'e1.mp4', cosKey: 'k1', uploadUrl: 'https://cos/1' },
        { mediaId: 2, fileName: 'e2.mp4', cosKey: 'k2', uploadUrl: 'https://cos/2' },
      ],
    })
    mockedPut.mockRejectedValueOnce(new Error('网络中断'))
    const { result } = renderHook(() => useKbUploadQueue(1))

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

  it('ignores unsupported files and requires a source', () => {
    const { result } = renderHook(() => useKbUploadQueue(1))
    expect(result.current.start([makeFile('notes.txt')])).toBe(0)

    const { result: noSource } = renderHook(() => useKbUploadQueue(null))
    expect(noSource.current.start([makeFile('e1.mp4')])).toBe(0)
    expect(mockedInit).not.toHaveBeenCalled()
  })
})
