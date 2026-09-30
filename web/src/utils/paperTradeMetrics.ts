/**
 * 模拟盘账户的资金指标推导（纯函数，前后端口径的唯一下沉点）。
 *
 * 当日盈亏 = 实时 nav − 前一快照 nav − 两快照间出入金增量。lastInout 是
 * 账户最后一笔出入金而非当日，误用会把历史入金全数计成盈亏（-20 万事故）。
 */
import type { ApiPaperTradeCash, ApiPaperTradeNavPoint } from '@ai-invest/shared'

import { bjNow } from '@/utils/beijing'
import { DATE_FORMAT } from '@/utils/formatters'

export interface DailyPnl {
  dayPnl: number | null
  dayPnlPct: number | null
}

export interface CumPnl {
  pnl: number | null
  pnlPct: number | null
}

/** 累计盈亏 = nav − 累计出入金（百分比分母 cumInout）；模拟盘页与 Agent 页同口径。 */
export function cumPnl(cash: Pick<ApiPaperTradeCash, 'nav' | 'cumInout'> | null | undefined): CumPnl {
  const nav = cash?.nav
  const cumInout = cash?.cumInout != null ? Number(cash.cumInout) : null
  if (nav == null || cumInout == null) return { pnl: null, pnlPct: null }
  const pnl = Number(nav) - cumInout
  const pnlPct = cumInout !== 0 ? (pnl / cumInout) * 100 : null
  return { pnl, pnlPct }
}

export function dailyPnl(
  items: ApiPaperTradeNavPoint[] | undefined,
  cash: Pick<ApiPaperTradeCash, 'nav' | 'cumInout'> | null | undefined,
): DailyPnl {
  const nav = cash?.nav
  const todayStr = bjNow().format(DATE_FORMAT)
  const prevPoint = [...(items ?? [])]
    .reverse()
    .find((p) => p.tradeDate < todayStr)
  if (nav == null || prevPoint?.nav == null) return { dayPnl: null, dayPnlPct: null }
  const liveCumInout = cash?.cumInout != null ? Number(cash.cumInout) : 0
  const dayBase = prevPoint.nav + liveCumInout - (prevPoint.cumInout ?? 0)
  const dayPnl = Number(nav) - dayBase
  const dayPnlPct = dayBase !== 0 ? (dayPnl / dayBase) * 100 : null
  return { dayPnl, dayPnlPct }
}
