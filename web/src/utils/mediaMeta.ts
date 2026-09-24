const PROBE_TIMEOUT_MS = 10_000

/**
 * 浏览器本地读取音视频时长（秒，取整）；元数据加载失败或超时返回 null。
 * 费用预估依赖该值（登记时随 init 请求入库，避免转写前时长未知）。
 */
export function probeMediaDuration(
  file: File,
  kind: 'video' | 'audio'
): Promise<number | null> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file)
    const el = document.createElement(kind === 'audio' ? 'audio' : 'video')
    let settled = false
    const done = (value: number | null) => {
      if (settled) return
      settled = true
      URL.revokeObjectURL(url)
      resolve(value)
    }
    el.preload = 'metadata'
    el.onloadedmetadata = () =>
      done(
        Number.isFinite(el.duration) && el.duration > 0
          ? Math.round(el.duration)
          : null
      )
    el.onerror = () => done(null)
    window.setTimeout(() => done(null), PROBE_TIMEOUT_MS)
    el.src = url
  })
}
