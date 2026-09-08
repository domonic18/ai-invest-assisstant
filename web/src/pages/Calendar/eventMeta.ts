import type { CalendarEvent } from '@ai-invest/shared'

export const DOW_LABELS_SUN_FIRST = ['日', '一', '二', '三', '四', '五', '六']

const SOURCE_LABELS: Record<string, string> = {
  cls: '财联社日历',
  fomc: '固定日程（Fed）',
  bls: '固定日程（BLS）',
}

export function sourceLabel(source: string | null): string {
  if (!source) return '—'
  return SOURCE_LABELS[source] ?? source
}

const STOCK_CODE_RE = /\b(\d{6})\b/

/** relatedSymbols 形如「宁德时代 300750」或宏观代码（US10Y），仅提取 6 位 A 股代码。 */
export function extractStockCodes(symbols: string[]): string[] {
  return symbols
    .map((s) => s.match(STOCK_CODE_RE)?.[1])
    .filter((code): code is string => Boolean(code))
}

export function eventHitsWatchlist(
  event: CalendarEvent,
  watchlistCodes: Set<string>,
): boolean {
  if (watchlistCodes.size === 0 || event.relatedSymbols.length === 0) return false
  return extractStockCodes(event.relatedSymbols).some((code) =>
    watchlistCodes.has(code),
  )
}
