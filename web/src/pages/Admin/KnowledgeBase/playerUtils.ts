/** 播放器/阅读器共享纯常量与函数（组件文件仅导出组件，react-refresh 约束）。 */

/** 凭证到期前提前刷新的余量（秒），避开边界 401（播放器与阅读器共用）。 */
export const TOKEN_REFRESH_MARGIN_SECONDS = 120

export interface VttCue {
  startMs: number
  endMs: number
  text: string
}

const VTT_TIMING = /^(\d{2,}):(\d{2}):(\d{2})[.,](\d{3}) --> (\d{2,}):(\d{2}):(\d{2})[.,](\d{3})/

function vttPartToMs(h: string, m: string, s: string, ms: string): number {
  return Number(h) * 3_600_000 + Number(m) * 60_000 + Number(s) * 1000 + Number(ms)
}

/** 解析 WebVTT 文本为字幕句列表（时间轴行 + 紧随文本行）。 */
export function parseVttCues(vtt: string): VttCue[] {
  const cues: VttCue[] = []
  const lines = vtt.split(/\r?\n/)
  for (let i = 0; i < lines.length; i++) {
    const match = VTT_TIMING.exec(lines[i])
    if (!match) continue
    const startMs = vttPartToMs(match[1], match[2], match[3], match[4])
    const endMs = vttPartToMs(match[5], match[6], match[7], match[8])
    const text: string[] = []
    for (let j = i + 1; j < lines.length; j++) {
      if (!lines[j].trim()) break
      text.push(lines[j])
      i = j
    }
    if (text.length > 0) cues.push({ startMs, endMs, text: text.join(' ') })
  }
  return cues
}

function pad(n: number): string {
  return String(Math.floor(n)).padStart(2, '0')
}

export function fmtClock(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000)
  const hours = Math.floor(totalSeconds / 3600)
  return hours > 0
    ? `${hours}:${pad((totalSeconds % 3600) / 60)}:${pad(totalSeconds % 60)}`
    : `${pad(totalSeconds / 60)}:${pad(totalSeconds % 60)}`
}
