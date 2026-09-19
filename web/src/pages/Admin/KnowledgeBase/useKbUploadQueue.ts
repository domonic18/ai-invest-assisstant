import { useCallback, useRef, useState } from 'react'

import type { ApiKbMediaInitItem } from '@ai-invest/shared'
import { KB_MULTIPART_THRESHOLD_BYTES } from '@ai-invest/shared'

import {
  confirmKbMediaUploaded,
  initKbMediaUploads,
  putFileToCos,
} from '@/api/adminKb'
import { computeFileMd5 } from '@/utils/fileHash'
import {
  clearStoredSession,
  uploadMultipartParts,
} from '@/utils/multipartUpload'

export type UploadItemStatus =
  | 'hashing'
  | 'uploading'
  | 'confirming'
  | 'done'
  | 'skipped'
  | 'failed'

export interface UploadItem {
  uid: string
  fileName: string
  relativePath: string
  size: number
  status: UploadItemStatus
  mediaId: number | null
  error: string | null
}

interface QueueEntry {
  uid: string
  file: File
  relativePath: string
  hash?: string
}

const VIDEO_EXT = new Set(['mp4', 'mkv', 'mov', 'avi', 'webm', 'flv', 'ts', 'm4v'])
const AUDIO_EXT = new Set(['mp3', 'm4a', 'wav', 'aac', 'flac', 'opus', 'ogg'])
const BOOK_EXT = new Set(['pdf', 'epub'])

/** 上传并发 lane 数（哈希在 Worker 单路串行，与上传流水线重叠）。 */
const UPLOAD_CONCURRENCY = 3

export function inferMediaKind(fileName: string): ApiKbMediaInitItem['mediaKind'] | null {
  const ext = fileName.split('.').pop()?.toLowerCase() ?? ''
  if (VIDEO_EXT.has(ext)) return 'video'
  if (AUDIO_EXT.has(ext)) return 'audio'
  if (BOOK_EXT.has(ext)) return 'book'
  return null
}

function errText(err: unknown): string {
  if (err instanceof Error && err.message === 'Network Error') {
    return '无法连接文件直传端点：请检查 MINIO_PUBLIC_ENDPOINT 是否为当前浏览器可达的 MinIO 地址（公网访问需在路由器放行对应端口）'
  }
  return err instanceof Error ? err.message : String(err)
}

/**
 * 目录直传队列（文件级独立 + 流水线并发，仿网盘批量上传）：
 * 哈希 Worker 单路串行，每算完一个即进 3 路上传池（大文件分片直传 +
 * 断点续传，小文件单 PUT）；批内同哈希后到副本标 skipped，库内冲突由
 * init 返回 conflictWith 跳过；失败项单条/整批重试（复用哈希，分片续传）。
 * 进度写 ref，由 rAF 循环节流拷贝进 state。
 */
export function useKbUploadQueue(sourceId: number | null) {
  const [items, setItems] = useState<UploadItem[]>([])
  const [progress, setProgress] = useState<Record<string, number>>({})
  const [running, setRunning] = useState(false)
  const progressRef = useRef<Map<string, number>>(new Map())
  const runningRef = useRef(false)
  const entriesRef = useRef<Map<string, QueueEntry>>(new Map())

  const setItemStatus = useCallback(
    (uid: string, patch: Partial<UploadItem>) => {
      setItems((prev) =>
        prev.map((it) => (it.uid === uid ? { ...it, ...patch } : it))
      )
    },
    []
  )

  // 单文件上传段：init（批内=单条，冲突即 skipped）→ 分片/整传 → confirm
  const processEntry = useCallback(
    async (entry: QueueEntry) => {
      const mediaKind = inferMediaKind(entry.file.name)
      if (!mediaKind) {
        setItemStatus(entry.uid, {
          status: 'failed',
          error: `不支持的文件类型：${entry.file.name}`,
        })
        return
      }
      let result
      try {
        const response = await initKbMediaUploads(sourceId as number, {
          items: [
            {
              fileName: entry.file.name,
              relativePath: entry.relativePath,
              size: entry.file.size,
              hash: entry.hash as string,
              mediaKind,
            },
          ],
        })
        result = response.items[0]
      } catch (err) {
        setItemStatus(entry.uid, { status: 'failed', error: errText(err) })
        return
      }
      if (!result) {
        setItemStatus(entry.uid, { status: 'failed', error: '服务端返回为空' })
        return
      }
      if (result.conflictWith) {
        setItemStatus(entry.uid, {
          status: 'skipped',
          error: `与${result.conflictWith}内容相同，已跳过`,
        })
        return
      }
      setItemStatus(entry.uid, { status: 'uploading', mediaId: result.mediaId })
      try {
        if (entry.file.size > KB_MULTIPART_THRESHOLD_BYTES) {
          await uploadMultipartParts({
            file: entry.file,
            hash: entry.hash as string,
            mediaId: result.mediaId as number,
            onProgress: (done, total) =>
              progressRef.current.set(
                entry.uid,
                Math.round((done / total) * 100)
              ),
          })
        } else {
          await putFileToCos(result.uploadUrl as string, entry.file, (pct) =>
            progressRef.current.set(entry.uid, pct)
          )
        }
        setItemStatus(entry.uid, { status: 'confirming' })
        await confirmKbMediaUploaded(result.mediaId as number)
        if (entry.hash) clearStoredSession(entry.hash)
        progressRef.current.set(entry.uid, 100)
        setItemStatus(entry.uid, { status: 'done' })
      } catch (err) {
        setItemStatus(entry.uid, { status: 'failed', error: errText(err) })
      }
    },
    [setItemStatus, sourceId]
  )

  const runEntries = useCallback(
    async (entries: QueueEntry[]) => {
      if (!sourceId || entries.length === 0) return
      runningRef.current = true
      setRunning(true)
      let raf = 0
      const flush = () => {
        setProgress(Object.fromEntries(progressRef.current))
        raf = requestAnimationFrame(flush)
      }
      raf = requestAnimationFrame(flush)
      try {
        const seen = new Map<string, string>()
        const ready: QueueEntry[] = []
        let active = 0
        let hashDone = false
        let drainedResolve: (() => void) | null = null
        const maybeDrained = () => {
          if (hashDone && active === 0 && ready.length === 0) drainedResolve?.()
        }
        const pump = () => {
          while (active < UPLOAD_CONCURRENCY && ready.length > 0) {
            const entry = ready.shift() as QueueEntry
            active++
            void processEntry(entry)
              .catch(() => undefined)
              .finally(() => {
                active--
                pump()
                maybeDrained()
              })
          }
          maybeDrained()
        }
        const drained = new Promise<void>((resolve) => {
          drainedResolve = resolve
        })

        // 阶段一（串行）：逐文件哈希（Worker），完成后即刻入上传池——哈希与上传流水线重叠
        for (const entry of entries) {
          if (entry.hash == null) {
            try {
              entry.hash = await computeFileMd5(entry.file, (pct) =>
                progressRef.current.set(entry.uid, pct)
              )
            } catch (err) {
              setItemStatus(entry.uid, { status: 'failed', error: errText(err) })
              continue
            }
          }
          const first = seen.get(entry.hash)
          if (first != null) {
            setItemStatus(entry.uid, {
              status: 'skipped',
              error: `与批内「${first}」内容相同，已跳过`,
            })
            continue
          }
          seen.set(entry.hash, entry.file.name)
          ready.push(entry)
          pump()
        }
        hashDone = true
        pump()
        await drained
      } finally {
        cancelAnimationFrame(raf)
        setProgress(Object.fromEntries(progressRef.current))
        runningRef.current = false
        setRunning(false)
      }
    },
    [processEntry, setItemStatus, sourceId]
  )

  const start = useCallback(
    (files: File[]) => {
      if (!sourceId) return 0
      const queue: QueueEntry[] = files
        .filter((file) => inferMediaKind(file.name) !== null)
        .map((file, i) => ({
          uid: `${Date.now()}-${i}-${file.name}`,
          file,
          relativePath:
            (file as File & { webkitRelativePath?: string }).webkitRelativePath ||
            file.name,
        }))
      if (queue.length === 0) return 0
      for (const entry of queue) entriesRef.current.set(entry.uid, entry)
      setItems((prev) => [
        ...prev,
        ...queue.map((q) => ({
          uid: q.uid,
          fileName: q.file.name,
          relativePath: q.relativePath,
          size: q.file.size,
          status: 'hashing' as UploadItemStatus,
          mediaId: null,
          error: null,
        })),
      ])
      void runEntries(queue)
      return queue.length
    },
    [runEntries, sourceId]
  )

  // 重试失败项：复用已算哈希重走 init（分片上传由服务端 list_parts 续传）
  const retry = useCallback(
    async (uid?: string) => {
      if (!sourceId || runningRef.current) return
      const targets = (
        uid
          ? [entriesRef.current.get(uid)]
          : items
              .filter((it) => it.status === 'failed')
              .map((it) => entriesRef.current.get(it.uid))
      ).filter((entry): entry is QueueEntry => entry != null)
      if (targets.length === 0) return
      for (const entry of targets) {
        setItemStatus(entry.uid, {
          status: entry.hash != null ? 'uploading' : 'hashing',
          error: null,
        })
      }
      await runEntries(targets)
    },
    [items, runEntries, setItemStatus, sourceId]
  )

  const clear = useCallback(() => {
    if (runningRef.current) return
    const removable = new Set(
      items.filter((it) => it.status === 'done' || it.status === 'skipped').map((it) => it.uid)
    )
    for (const uid of removable) entriesRef.current.delete(uid)
    setItems((prev) => prev.filter((it) => !removable.has(it.uid)))
    for (const uid of removable) progressRef.current.delete(uid)
    setProgress(Object.fromEntries(progressRef.current))
  }, [items])

  return { items, progress, running, start, retry, clear }
}
