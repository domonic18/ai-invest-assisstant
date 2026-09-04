import dayjs from 'dayjs'
import type { Dayjs } from 'dayjs'

import type { IndexAuctionTrend } from '@/api/auction'

// 交易日 ≈ 自然日 × 1.5（含周末与节假日冗余，图表只展示有数据的交易日）
export const TRADING_DAY_PRESETS: Array<{ label: string; value: number }> = [
  { label: '近 5 个交易日', value: 5 },
  { label: '近 10 个交易日', value: 10 },
  { label: '近 20 个交易日', value: 20 },
  { label: '近 60 个交易日', value: 60 },
]

export function presetToRange(days: number): [Dayjs, Dayjs] {
  return [dayjs().subtract(Math.round(days * 1.5), 'day'), dayjs()]
}

/** 竞价特征分级口径：量比 = 当日三指数合计 / 前 5 日合计均值。 */
export const HIGH_VOLUME_RATIO = 1.2
export const LOW_VOLUME_RATIO = 0.8
const RATIO_WINDOW = 5

export type AuctionFeature = 'high' | 'low' | 'normal'

export interface AuctionDayStat {
  date: string
  values: Array<number | null>
  total: number | null
  /** 前 5 日合计均值比；窗口不足为 null。 */
  ratio: number | null
  feature: AuctionFeature | null
}

export function buildDailyStats(data: IndexAuctionTrend): AuctionDayStat[] {
  const raw = data.dates.map((date, i) => {
    const values = data.series.map((s) => s.values[i] ?? null)
    const nums = values.filter((v): v is number => v !== null)
    return {
      date,
      values,
      total: nums.length === values.length || nums.length > 0 ? nums.reduce((a, b) => a + b, 0) : null,
      ratio: null as number | null,
      feature: null as AuctionFeature | null,
    }
  })
  raw.forEach((row, i) => {
    if (row.total === null || i < RATIO_WINDOW) return
    const window = raw.slice(i - RATIO_WINDOW, i)
    const prevTotals = window.map((r) => r.total).filter((t): t is number => t !== null)
    if (prevTotals.length < RATIO_WINDOW) return
    const avg = prevTotals.reduce((a, b) => a + b, 0) / prevTotals.length
    if (avg <= 0) return
    row.ratio = row.total / avg
    row.feature =
      row.ratio >= HIGH_VOLUME_RATIO
        ? 'high'
        : row.ratio <= LOW_VOLUME_RATIO
          ? 'low'
          : 'normal'
  })
  return raw
}

export function countFeature(stats: AuctionDayStat[], feature: AuctionFeature): number {
  return stats.filter((row) => row.feature === feature).length
}

const FEATURE_LABEL: Record<AuctionFeature, string> = {
  high: '放量',
  low: '缩量',
  normal: '常态',
}

export function featureLabel(feature: AuctionFeature | null): string {
  return feature ? FEATURE_LABEL[feature] : '-'
}

/** 导出当前查询区间的日统计 CSV（UTF-8 BOM，Excel 直开）。 */
export function statsToCsv(data: IndexAuctionTrend, stats: AuctionDayStat[]): string {
  const header = ['日期', ...data.series.map((s) => `${s.name}竞价额(亿)`), '合计(亿)', '量比', '特征']
  const lines = stats.map((row) =>
    [
      row.date,
      ...row.values.map((v) => (v === null ? '' : v.toFixed(2))),
      row.total === null ? '' : row.total.toFixed(2),
      row.ratio === null ? '' : row.ratio.toFixed(2),
      featureLabel(row.feature),
    ].join(','),
  )
  // UTF-8 BOM 前缀，保证 Excel 直接打开不乱码
  return `\uFEFF${[header.join(','), ...lines].join('\n')}`
}

export function downloadCsv(filename: string, csv: string): void {
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}
