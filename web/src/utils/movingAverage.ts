/** 简单移动平均：窗口不足或窗口内存在 null 时该点为 null。 */
export function movingAverage(
  values: (number | null)[],
  window: number,
): (number | null)[] {
  const result: (number | null)[] = new Array(values.length).fill(null)
  let sum = 0
  let nullCount = 0
  for (let i = 0; i < values.length; i++) {
    const incoming = values[i]
    if (incoming == null) nullCount++
    else sum += incoming
    if (i >= window) {
      const outgoing = values[i - window]
      if (outgoing == null) nullCount--
      else sum -= outgoing
    }
    if (i >= window - 1 && nullCount === 0) {
      result[i] = sum / window
    }
  }
  return result
}
