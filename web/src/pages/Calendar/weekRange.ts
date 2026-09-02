import type { Dayjs } from 'dayjs'

/** 取 anchor 所在周的周一（dayjs 默认周日为一周起点，这里显式按周一组织）。 */
export function mondayOf(anchor: Dayjs): Dayjs {
  const dow = anchor.day() // 0=周日
  return dow === 0 ? anchor.subtract(6, 'day') : anchor.subtract(dow - 1, 'day')
}
