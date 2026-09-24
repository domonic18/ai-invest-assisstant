import SparkMD5 from 'spark-md5'

const CHUNK_SIZE = 8 * 1024 * 1024

/** 文件 MD5 计算 Worker：主线程 postMessage({ file })，回报 progress/done/error。 */
self.onmessage = async (e: MessageEvent<{ file: File }>) => {
  const { file } = e.data
  try {
    const spark = new SparkMD5.ArrayBuffer()
    for (let offset = 0; offset < file.size; offset += CHUNK_SIZE) {
      const buffer = await file.slice(offset, offset + CHUNK_SIZE).arrayBuffer()
      spark.append(buffer)
      self.postMessage({
        type: 'progress',
        pct: Math.min(100, Math.round(((offset + CHUNK_SIZE) / file.size) * 100)),
      })
    }
    self.postMessage({ type: 'done', hash: spark.end() })
  } catch (err) {
    self.postMessage({
      type: 'error',
      message: err instanceof Error ? err.message : String(err),
    })
  }
}
