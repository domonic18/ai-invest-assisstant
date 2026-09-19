import type { ApiKbUploadSessionResponse } from '@ai-invest/shared'
import { KB_MULTIPART_THRESHOLD_BYTES, KB_PART_SIZE_BYTES } from '@ai-invest/shared'

import {
  createKbUploadSession,
  putPartToCos,
} from '@/api/adminKb'
import { computeBlobMd5 } from '@/utils/fileHash'

const PART_CONCURRENCY = 3
const PART_ATTEMPTS = 3

export { KB_MULTIPART_THRESHOLD_BYTES, KB_PART_SIZE_BYTES }

export function planPartCount(fileSize: number, partSize: number): number {
  return Math.max(1, Math.ceil(fileSize / partSize))
}

// ---- 断点续传登记（localStorage，uploadId 仅为提示；服务端 list_parts 是真相）----

interface StoredSession {
  mediaId: number
  uploadId: string
  partSize: number
  fingerprint: { name: string; size: number; lastModified: number }
}

function sessionKey(hash: string): string {
  return `kb-upload-session:${hash}`
}

function fingerprintOf(file: File): StoredSession['fingerprint'] {
  return { name: file.name, size: file.size, lastModified: file.lastModified }
}

export function loadStoredSession(hash: string, file: File): StoredSession | null {
  try {
    const raw = localStorage.getItem(sessionKey(hash))
    if (!raw) return null
    const stored = JSON.parse(raw) as StoredSession
    const fp = fingerprintOf(file)
    if (
      stored.fingerprint?.name === fp.name &&
      stored.fingerprint?.size === fp.size &&
      stored.fingerprint?.lastModified === fp.lastModified
    ) {
      return stored
    }
  } catch {
    // 登记损坏按无续传处理
  }
  return null
}

function saveStoredSession(hash: string, session: StoredSession): void {
  try {
    localStorage.setItem(sessionKey(hash), JSON.stringify(session))
  } catch {
    // 隐私模式等存储不可用时放弃续传登记
  }
}

export function clearStoredSession(hash: string): void {
  try {
    localStorage.removeItem(sessionKey(hash))
  } catch {
    // 同上
  }
}

async function uploadPartWithRetry(
  file: File,
  partNumber: number,
  partSize: number,
  url: string
): Promise<void> {
  const chunk = file.slice((partNumber - 1) * partSize, partNumber * partSize)
  let lastError: unknown = null
  for (let attempt = 1; attempt <= PART_ATTEMPTS; attempt++) {
    try {
      const etag = await putPartToCos(url, chunk)
      if (etag) {
        const expected = await computeBlobMd5(chunk)
        if (etag.replace(/"/g, '').toLowerCase() !== expected) {
          throw new Error(`分片 ${partNumber} 校验不符`)
        }
      }
      return
    } catch (err) {
      lastError = err
    }
  }
  throw lastError instanceof Error ? lastError : new Error(`分片 ${partNumber} 上传失败`)
}

/**
 * 大文件分片直传：创建/续传会话（已完成分片由服务端返回，断点续传），
 * 缺失分片 3 路并行上传（逐片 ETag 核对 + 单片重试），不含 confirm。
 */
export async function uploadMultipartParts(opts: {
  file: File
  hash: string
  mediaId: number
  onProgress?: (done: number, total: number) => void
}): Promise<void> {
  const { file, hash, mediaId, onProgress } = opts
  const stored = loadStoredSession(hash, file)
  const session: ApiKbUploadSessionResponse = await createKbUploadSession(mediaId, {
    partSize: KB_PART_SIZE_BYTES,
    partCount: planPartCount(file.size, KB_PART_SIZE_BYTES),
    resumeUploadId: stored?.uploadId ?? null,
  })
  saveStoredSession(hash, {
    mediaId,
    uploadId: session.uploadId,
    partSize: session.partSize,
    fingerprint: fingerprintOf(file),
  })

  let done = session.completedParts.length
  onProgress?.(done, session.partCount)

  const pending = session.partUrls
  let cursor = 0
  const lanes = Array.from(
    { length: Math.min(PART_CONCURRENCY, pending.length) },
    () =>
      (async () => {
        while (cursor < pending.length) {
          const part = pending[cursor++]
          await uploadPartWithRetry(file, part.partNumber, session.partSize, part.url)
          done += 1
          onProgress?.(done, session.partCount)
        }
      })()
  )
  await Promise.all(lanes)
}
