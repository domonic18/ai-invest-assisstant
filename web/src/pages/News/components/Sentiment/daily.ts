/** 账号卡按日多空时序的纯展示逻辑：多账号按日合并与总量统计。 */
import type { ApiSocialAccountCard, ApiSocialDailyStance } from '@ai-invest/shared'

/** 多账号按日合并（缺失日不计），按日期升序。 */
export function mergeAccountDaily(
  accounts: ApiSocialAccountCard[],
): ApiSocialDailyStance[] {
  const byDay = new Map<string, ApiSocialDailyStance>()
  for (const account of accounts) {
    for (const row of account.daily) {
      const current =
        byDay.get(row.date) ??
        ({ date: row.date, bullish: 0, bearish: 0, neutral: 0 } as ApiSocialDailyStance)
      current.bullish += row.bullish
      current.bearish += row.bearish
      current.neutral += row.neutral
      byDay.set(row.date, current)
    }
  }
  return [...byDay.values()].sort((a, b) => a.date.localeCompare(b.date))
}

/** 多空总量统计（窗口内）。 */
export function sumStance(rows: ApiSocialDailyStance[]): {
  bullish: number
  bearish: number
  neutral: number
} {
  return rows.reduce(
    (acc, row) => ({
      bullish: acc.bullish + row.bullish,
      bearish: acc.bearish + row.bearish,
      neutral: acc.neutral + row.neutral,
    }),
    { bullish: 0, bearish: 0, neutral: 0 },
  )
}
