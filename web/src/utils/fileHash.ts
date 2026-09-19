import SparkMD5 from 'spark-md5'

const HASH_CHUNK_SIZE = 8 * 1024 * 1024

function sliceToArrayBuffer(blob: Blob): Promise<ArrayBuffer> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as ArrayBuffer)
    reader.onerror = () => reject(reader.error ?? new Error('文件读取失败'))
    reader.readAsArrayBuffer(blob)
  })
}

async function computeInline(
  file: File,
  onProgress?: (pct: number) => void
): Promise<string> {
  const spark = new SparkMD5.ArrayBuffer()
  for (let offset = 0; offset < file.size; offset += HASH_CHUNK_SIZE) {
    const chunk = await sliceToArrayBuffer(file.slice(offset, offset + HASH_CHUNK_SIZE))
    spark.append(chunk)
    onProgress?.(Math.min(100, Math.round(((offset + HASH_CHUNK_SIZE) / file.size) * 100)))
  }
  return spark.end()
}

function computeInWorker(
  file: File,
  onProgress?: (pct: number) => void
): Promise<string> {
  return new Promise((resolve, reject) => {
    const worker = new Worker(
      new URL('../workers/fileMd5.worker.ts', import.meta.url),
      { type: 'module' }
    )
    worker.onmessage = (e: MessageEvent) => {
      const data = e.data as
        | { type: 'progress'; pct: number }
        | { type: 'done'; hash: string }
        | { type: 'error'; message: string }
      if (data.type === 'progress') {
        onProgress?.(data.pct)
      } else if (data.type === 'done') {
        worker.terminate()
        resolve(data.hash)
      } else {
        worker.terminate()
        reject(new Error(data.message))
      }
    }
    worker.onerror = () => {
      worker.terminate()
      reject(new Error('哈希 Worker 加载失败'))
    }
    worker.postMessage({ file })
  })
}

/**
 * 增量计算文件 MD5（与 COS etag 对齐，confirm_uploaded 服务端核对依据）。
 * 优先在 Web Worker 计算（大文件不阻塞 UI），不可用时回退主线程内联计算。
 */
export async function computeFileMd5(
  file: File,
  onProgress?: (pct: number) => void
): Promise<string> {
  if (typeof Worker === 'undefined') return computeInline(file, onProgress)
  try {
    return await computeInWorker(file, onProgress)
  } catch {
    return computeInline(file, onProgress)
  }
}

/** 计算分片（Blob）MD5，用于逐片 ETag 核对。 */
export async function computeBlobMd5(blob: Blob): Promise<string> {
  const spark = new SparkMD5.ArrayBuffer()
  spark.append(await sliceToArrayBuffer(blob))
  return spark.end()
}
