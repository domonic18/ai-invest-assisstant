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

/**
 * 增量计算文件 MD5（与 COS etag 对齐，confirm_uploaded 服务端核对依据）。
 * 分片读取避免大视频整文件载入内存。
 */
export async function computeFileMd5(
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
