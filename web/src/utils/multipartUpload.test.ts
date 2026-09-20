import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/adminKb', () => ({
  createKbUploadSession: vi.fn(),
  putPartToCos: vi.fn(),
}))

import { createKbUploadSession, putPartToCos } from '@/api/adminKb'

import { computeBlobMd5 } from './fileHash'
import {
  clearStoredSession,
  KB_PART_SIZE_BYTES,
  loadStoredSession,
  planPartCount,
  uploadMultipartParts,
} from './multipartUpload'

const mockedCreate = vi.mocked(createKbUploadSession)
const mockedPutPart = vi.mocked(putPartToCos)

function makeFile(name: string, size: number): File {
  const file = new File([new Uint8Array(8).fill(66)], name, { type: 'video/mp4' })
  Object.defineProperty(file, 'size', { value: size })
  return file
}

function sessionOf(
  mediaId: number,
  partCount: number,
  partUrls: { partNumber: number; url: string }[],
  completedParts: { partNumber: number; etag: string; size: number }[] = []
) {
  return {
    mediaId,
    uploadId: 'uid-1',
    partSize: KB_PART_SIZE_BYTES,
    partCount,
    completedParts,
    partUrls,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
})

describe('planPartCount', () => {
  it('ceil-divides with minimum 1', () => {
    expect(planPartCount(0, KB_PART_SIZE_BYTES)).toBe(1)
    expect(planPartCount(1, KB_PART_SIZE_BYTES)).toBe(1)
    expect(planPartCount(KB_PART_SIZE_BYTES + 1, KB_PART_SIZE_BYTES)).toBe(2)
  })
})

describe('uploadMultipartParts', () => {
  it('creates a fresh session and uploads only missing parts in order', async () => {
    const file = makeFile('big.mp4', KB_PART_SIZE_BYTES * 2)
    const hash = 'a'.repeat(32)
    mockedCreate.mockResolvedValue(
      sessionOf(7, 2, [
        { partNumber: 1, url: 'https://cos/p1' },
        { partNumber: 2, url: 'https://cos/p2' },
      ])
    )
    mockedPutPart.mockImplementation(async (_url, chunk) => computeBlobMd5(chunk))

    const progress: Array<[number, number]> = []
    await uploadMultipartParts({
      file,
      hash,
      mediaId: 7,
      onProgress: (done, total) => progress.push([done, total]),
    })

    expect(mockedCreate).toHaveBeenCalledWith(7, {
      partSize: KB_PART_SIZE_BYTES,
      partCount: 2,
      resumeUploadId: null,
    })
    expect(mockedPutPart).toHaveBeenCalledTimes(2)
    expect(progress[progress.length - 1]).toEqual([2, 2])
    // 会话保留至 confirm 成功后由队列清除（confirm 失败可续传重试）
    expect(loadStoredSession(hash, file)?.uploadId).toBe('uid-1')
  })

  it('resumes from stored session: passes resumeUploadId and skips completed parts', async () => {
    const file = makeFile('big.mp4', KB_PART_SIZE_BYTES * 3)
    const hash = 'b'.repeat(32)
    localStorage.setItem(
      `kb-upload-session:${hash}`,
      JSON.stringify({
        mediaId: 7,
        uploadId: 'uid-stored',
        partSize: KB_PART_SIZE_BYTES,
        fingerprint: { name: file.name, size: file.size, lastModified: file.lastModified },
      })
    )
    mockedCreate.mockResolvedValue(
      sessionOf(7, 3, [{ partNumber: 3, url: 'https://cos/p3' }], [
        { partNumber: 1, etag: 'e1', size: KB_PART_SIZE_BYTES },
        { partNumber: 2, etag: 'e2', size: KB_PART_SIZE_BYTES },
      ])
    )
    mockedPutPart.mockImplementation(async (_url, chunk) => computeBlobMd5(chunk))

    const progress: Array<[number, number]> = []
    await uploadMultipartParts({
      file,
      hash,
      mediaId: 7,
      onProgress: (done, total) => progress.push([done, total]),
    })

    expect(mockedCreate).toHaveBeenCalledWith(7, {
      partSize: KB_PART_SIZE_BYTES,
      partCount: 3,
      resumeUploadId: 'uid-stored',
    })
    // 只传缺失的第 3 片
    expect(mockedPutPart).toHaveBeenCalledTimes(1)
    expect(progress[0]).toEqual([2, 3])
    expect(progress[progress.length - 1]).toEqual([3, 3])
  })

  it('ignores stale stored sessions with mismatched fingerprints', () => {
    const file = makeFile('big.mp4', 100)
    const hash = 'c'.repeat(32)
    localStorage.setItem(
      `kb-upload-session:${hash}`,
      JSON.stringify({
        mediaId: 7,
        uploadId: 'uid-stale',
        partSize: KB_PART_SIZE_BYTES,
        fingerprint: { name: 'other.mp4', size: 100, lastModified: 1 },
      })
    )
    expect(loadStoredSession(hash, file)).toBeNull()
    clearStoredSession(hash)
    expect(localStorage.getItem(`kb-upload-session:${hash}`)).toBeNull()
  })

  it('retries a part on etag mismatch and surfaces failure after attempts', async () => {
    const file = makeFile('big.mp4', KB_PART_SIZE_BYTES)
    mockedCreate.mockResolvedValue(
      sessionOf(7, 1, [{ partNumber: 1, url: 'https://cos/p1' }])
    )
    // 永远返回不符的 etag：1 次首发 + PART_ATTEMPTS 内重试后抛错
    mockedPutPart.mockResolvedValue('deadbeef')

    await expect(
      uploadMultipartParts({ file, hash: 'd'.repeat(32), mediaId: 7 })
    ).rejects.toThrow('校验不符')
    expect(mockedPutPart).toHaveBeenCalledTimes(3)
  })
})
