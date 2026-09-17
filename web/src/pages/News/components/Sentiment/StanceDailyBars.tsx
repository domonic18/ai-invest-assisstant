/** 按日多空堆叠条：每日一列，段高按当日多/中/空占比；红多绿空（跟随涨跌配色）。 */

import type { ApiSocialDailyStance } from '@ai-invest/shared'

import { fallHex, riseHex } from '@/utils/formatters'

interface StanceDailyBarsProps {
  rows: ApiSocialDailyStance[]
  /** 堆叠条像素高度 */
  height?: number
  /** 是否显示 M/D 日期标签（汇总条开启，账号卡内关闭） */
  showDayLabel?: boolean
}

const NEUTRAL_BG = 'rgba(255, 255, 255, 0.16)'

export function StanceDailyBars({
  rows,
  height = 28,
  showDayLabel = false,
}: StanceDailyBarsProps) {
  if (!rows.length) return null
  return (
    <div className="flex items-end gap-1 min-w-0">
      {rows.map((row) => {
        const total = row.bullish + row.bearish + row.neutral
        const pct = (n: number) => `${(n / total) * 100}%`
        return (
          <div
            key={row.date}
            className="flex flex-col items-center gap-0.5 flex-1 min-w-0"
            title={`${row.date} · 多 ${row.bullish} / 中 ${row.neutral} / 空 ${row.bearish}`}
          >
            <div
              className="flex w-full max-w-[18px] flex-col overflow-hidden rounded-sm"
              style={{ height }}
            >
              {row.bullish > 0 && (
                <div style={{ height: pct(row.bullish), background: riseHex() }} />
              )}
              {row.neutral > 0 && (
                <div style={{ height: pct(row.neutral), background: NEUTRAL_BG }} />
              )}
              {row.bearish > 0 && (
                <div style={{ height: pct(row.bearish), background: fallHex() }} />
              )}
            </div>
            {showDayLabel && (
              <span className="text-[9px] opacity-40 whitespace-nowrap">
                {row.date.slice(5).replace('-', '/')}
              </span>
            )}
          </div>
        )
      })}
    </div>
  )
}
