/** 技术指标计算工具（纯前端）。 */

function _ema(values: (number | null)[], period: number): (number | null)[] {
  const alpha = 2 / (period + 1)
  const result: (number | null)[] = []
  let prevEma: number | null = null

  for (const value of values) {
    if (value == null) {
      result.push(prevEma)
      continue
    }
    prevEma = prevEma == null ? value : alpha * value + (1 - alpha) * prevEma
    result.push(prevEma)
  }

  return result
}

export interface MACDResult {
  dif: (number | null)[]
  dea: (number | null)[]
  macd: (number | null)[]
}

/**
 * 计算 MACD（12, 26, 9）。
 * 当某根 bar 的收盘价缺失时，DIF/DEA/MACD 取前一个有效值；
 * 序列开头不足 slow 根有效数据的位置输出 null。
 */
export function calculateMACD(
  closes: (number | null)[],
  fast = 12,
  slow = 26,
  signal = 9,
): MACDResult {
  const emaFast = _ema(closes, fast)
  const emaSlow = _ema(closes, slow)
  const dif: (number | null)[] = []
  let validCount = 0

  for (let i = 0; i < closes.length; i++) {
    if (closes[i] != null) {
      validCount++
    }
    const f = emaFast[i]
    const s = emaSlow[i]
    if (f != null && s != null && validCount >= slow) {
      dif.push(f - s)
    } else {
      dif.push(null)
    }
  }

  const dea = _ema(dif, signal)
  const macd: (number | null)[] = []

  for (let i = 0; i < dif.length; i++) {
    const d = dif[i]
    const e = dea[i]
    if (d != null && e != null) {
      macd.push(2 * (d - e))
    } else {
      macd.push(null)
    }
  }

  return { dif, dea, macd }
}

export interface KDJResult {
  k: (number | null)[]
  d: (number | null)[]
  j: (number | null)[]
}

/**
 * 计算 KDJ（默认 9, 3, 3）。
 * 窗口内存在 null 时输出 null；首根 bar 之前 K=D=50。
 */
export function calculateKDJ(
  highs: (number | null)[],
  lows: (number | null)[],
  closes: (number | null)[],
  n = 9,
  m1 = 3,
  m2 = 3,
): KDJResult {
  const k: (number | null)[] = []
  const d: (number | null)[] = []
  const j: (number | null)[] = []
  let prevK = 50
  let prevD = 50

  for (let i = 0; i < closes.length; i++) {
    if (i < n - 1) {
      k.push(null)
      d.push(null)
      j.push(null)
      continue
    }

    const windowHighs: number[] = []
    const windowLows: number[] = []
    let close: number | null = null
    for (let t = i - n + 1; t <= i; t++) {
      const h = highs[t]
      const l = lows[t]
      if (h == null || l == null) {
        break
      }
      windowHighs.push(h)
      windowLows.push(l)
      if (t === i) {
        close = closes[t]
      }
    }

    if (windowHighs.length < n || close == null) {
      k.push(null)
      d.push(null)
      j.push(null)
      continue
    }

    const highest = Math.max(...windowHighs)
    const lowest = Math.min(...windowLows)
    const range = highest - lowest

    let rsv: number
    if (range === 0) {
      rsv = 0
    } else {
      rsv = ((close - lowest) / range) * 100
    }

    const kt = ((m1 - 1) * prevK + rsv) / m1
    const dt = ((m2 - 1) * prevD + kt) / m2
    const jt = 3 * kt - 2 * dt

    k.push(kt)
    d.push(dt)
    j.push(jt)
    prevK = kt
    prevD = dt
  }

  return { k, d, j }
}
