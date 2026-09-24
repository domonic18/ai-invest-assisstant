import { describe, expect, it } from 'vitest'

import { computeFileMd5 } from './fileHash'

function makeFile(content: string, name = 'a.txt'): File {
  return new File([content], name, { type: 'text/plain' })
}

describe('computeFileMd5', () => {
  it('computes md5 matching known digest', async () => {
    // "hello world" 的标准 MD5
    const hash = await computeFileMd5(makeFile('hello world'))
    expect(hash).toBe('5eb63bbbe01eeed093cb22bb8f5acdc3')
  })

  it('crosses the 8MB chunk boundary without corruption', async () => {
    // 8MB+100 字节：跨一个分片边界
    const bytes = new Uint8Array(8 * 1024 * 1024 + 100).fill(65)
    const file = new File([bytes], 'big.bin')
    const hash = await computeFileMd5(file)
    // 与未分片的整体摘要一致（SparkMD5 对相同内容结果稳定）
    const SparkMD5 = (await import('spark-md5')).default
    const whole = new SparkMD5.ArrayBuffer()
    whole.append(bytes.buffer as ArrayBuffer)
    expect(hash).toBe(whole.end())
  })

  it('reports monotonic progress 0..100', async () => {
    const seen: number[] = []
    await computeFileMd5(makeFile('x'.repeat(100)), (pct) => seen.push(pct))
    expect(seen[0]).toBeGreaterThan(0)
    expect(seen[seen.length - 1]).toBe(100)
    for (let i = 1; i < seen.length; i++) {
      expect(seen[i]).toBeGreaterThanOrEqual(seen[i - 1])
    }
  })
})
