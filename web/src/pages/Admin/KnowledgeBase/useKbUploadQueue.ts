import { useCallback, useRef, useState } from 'react'

import type { ApiKbMediaInitItem } from '@ai-invest/shared'

import {
  confirmKbMediaUploaded,
  initKbMediaUploads,
  putFileToCos,
} from '@/api/adminKb'
import { computeFileMd5 } from '@/utils/fileHash'

export type UploadItemStatus = 'hashing' | 'uploading' | 'confirming' | 'done' | 'failed'

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

export function inferMediaKind(fileName: string): ApiKbMediaInitItem['mediaKind'] | null {
  const ext = fileName.split('.').pop()?.toLowerCase() ?? ''
  if (VIDEO_EXT.has(ext)) return 'video'
  if (AUDIO_EXT.has(ext)) return 'audio'
  if (BOOK_EXT.has(ext)) return 'book'
  return null
}

function errText(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

/**
 * 目录直传队列：批量 MD5 → init（建行+预签名）→ 逐文件 PUT COS → uploaded 核对。
 * 进度写 ref，由 rAF 循环节流拷贝进 state（onUploadProgress 高频触发不逐次渲染）。
 */
export function useKbUploadQueue(sourceId: number | null) {
  const [items, setItems] = useState<UploadItem[]>([])
  const [progress, setProgress] = useState<Record<string, number>>({})
  const [running, setRunning] = useState(false)
  const progressRef = useRef<Map<string, number>>(new Map())
  const runningRef = useRef(false)

  const setItemStatus = useCallback(
    (uid: string, patch: Partial<UploadItem>) => {
      setItems((prev) =>
        prev.map((it) => (it.uid === uid ? { ...it, ...patch } : it))
      )
    },
    []
  )

  const run = useCallback(
    async (queue: QueueEntry[]) => {
      if (!sourceId || queue.length === 0) return
      runningRef.current = true
      setRunning(true)

      let raf = 0
      const flush = () => {
        setProgress(Object.fromEntries(progressRef.current))
        raf = requestAnimationFrame(flush)
      }
      raf = requestAnimationFrame(flush)

      try {
        // 阶段一：逐文件增量 MD5（hash 与 COS etag 对齐，服务端核对依据）
        for (const entry of queue) {
          try {
            entry.hash = await computeFileMd5(entry.file, (pct) =>
              progressRef.current.set(entry.uid, pct)
            )
          } catch (err) {
            setItemStatus(entry.uid, { status: 'failed', error: errText(err) })
          }
        }
        const hashable = queue.filter((q) => q.hash != null)
        if (hashable.length === 0) return

        // 阶段二：批量 init（course 集号按序自动编号；哈希冲突整批 409）
        let results
        try {
          const initItems = hashable.map((q) => {
            const mediaKind = inferMediaKind(q.file.name)
            if (!mediaKind) throw new Error(`不支持的文件类型：${q.file.name}`)
            const item: ApiKbMediaInitItem = {
              fileName: q.file.name,
              relativePath: q.relativePath,
              size: q.file.size,
              hash: q.hash as string,
              mediaKind,
            }
            return item
          })
          results = (await initKbMediaUploads(sourceId, { items: initItems })).items
        } catch (err) {
          for (const q of hashable) {
            setItemStatus(q.uid, { status: 'failed', error: errText(err) })
          }
          return
        }

        // 阶段三：逐文件直传 COS + uploaded 服务端核对
        for (let i = 0; i < results.length; i++) {
          const result = results[i]
          const entry = hashable[i]
          setItemStatus(entry.uid, { status: 'uploading', mediaId: result.mediaId })
          try {
            await putFileToCos(result.uploadUrl, entry.file, (pct) =>
              progressRef.current.set(entry.uid, pct)
            )
            setItemStatus(entry.uid, { status: 'confirming' })
            await confirmKbMediaUploaded(result.mediaId)
            progressRef.current.set(entry.uid, 100)
            setItemStatus(entry.uid, { status: 'done' })
          } catch (err) {
            setItemStatus(entry.uid, { status: 'failed', error: errText(err) })
          }
        }
      } finally {
        cancelAnimationFrame(raf)
        setProgress(Object.fromEntries(progressRef.current))
        runningRef.current = false
        setRunning(false)
      }
    },
    [sourceId, setItemStatus]
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
      void run(queue)
      return queue.length
    },
    [run, sourceId]
  )

  const clear = useCallback(() => {
    if (runningRef.current) return
    setItems((prev) => prev.filter((it) => it.status !== 'done'))
    progressRef.current.clear()
    setProgress({})
  }, [])

  return { items, progress, running, start, clear }
}
