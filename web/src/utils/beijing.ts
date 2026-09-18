/** 北京墙钟唯一入口：dayjs utc 插件统一在此加载（禁止其他文件副作用式 extend）。
 * 领域日历语义（调度 cron、交易日、盘口状态）一律经本模块运算，与运行环境时区无关；
 * 时间戳渲染属于本地化语义，请走 utils/formatters。
 * 中国无夏令时，固定 UTC+8 恒等价于 Asia/Shanghai。 */

import dayjs, { type Dayjs } from 'dayjs'
import utc from 'dayjs/plugin/utc'

dayjs.extend(utc)

export const BJ_OFFSET_MIN = 480

/** 转为北京墙钟表示（UTC+8）。幂等：已是北京表示的对象原样返回，
 * 规避 dayjs utcOffset 对已转换对象重复调用的二次平移怪癖（非 +08 环境下墙钟漂移 8h）。 */
export function toBeijing(d: Dayjs): Dayjs {
  return d.utcOffset() === BJ_OFFSET_MIN ? d : d.utcOffset(BJ_OFFSET_MIN)
}

/** 当前北京墙钟。 */
export function bjNow(): Dayjs {
  return toBeijing(dayjs())
}

/** cron 日匹配的北京墙钟判定（标准语义：dom 与 dow 任一受限时取 OR，否则各自必须命中）。 */
export function bjDayMatches(
  p: { months: number[] | null; doms: number[] | null; dows: number[] | null },
  d: Dayjs,
): boolean {
  if (p.months && !p.months.includes(d.month() + 1)) return false
  const domOk = !p.doms || p.doms.includes(d.date())
  const dowOk = !p.dows || p.dows.includes(d.day())
  if (p.doms && p.dows) return domOk || dowOk
  return domOk && dowOk
}
