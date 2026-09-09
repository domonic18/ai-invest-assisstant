import { StarFilled, StarOutlined } from '@ant-design/icons'
import { Skeleton, Tag } from 'antd'

import { useStockKline } from '@/hooks/useStocks'
import {
  changeHex,
  formatAmount,
  riseHex,
  fallHex,
} from '@/utils/formatters'
import { deriveAmplitude, deriveBarChange, formatWanShou } from '@/utils/kline'
import type { Stock, StockQuote } from '@ai-invest/shared'

interface QuoteStripProps {
  stockCode: string
  stock?: Stock | null
  stockLoading?: boolean
  quote?: StockQuote | null
  quoteLoading?: boolean
  isWatched?: boolean
  onAddWatchlist: () => void
}

const TEXT_PRIMARY = '#f0f1f5'
const TEXT_TERTIARY = '#5c616e'

function signed(v: number | null, decimals = 2): string {
  if (v == null) return '--'
  return `${v > 0 ? '+' : ''}${v.toFixed(decimals)}`
}

function signedPct(v: number | null, decimals = 2): string {
  if (v == null) return '--'
  return `${v > 0 ? '+' : ''}${v.toFixed(decimals)}%`
}

export function QuoteStrip({
  stockCode,
  stock,
  stockLoading,
  quote,
  quoteLoading,
  isWatched,
  onAddWatchlist,
}: QuoteStripProps) {
  // 换手率/振幅取自最新日 K bar（sina 渠道 turnover 有值，amplitude 缺失时派生）
  const { data: kline } = useStockKline(stockCode, { period: 'daily', limit: 2 })
  const latestBar = kline?.bars[kline.bars.length - 1]
  const prevBar = kline && kline.bars.length > 1 ? kline.bars[kline.bars.length - 2] : undefined

  const turnoverText = latestBar?.turnoverRate != null
    ? `${latestBar.turnoverRate.toFixed(2)}%`
    : '--'
  const amplitude = latestBar
    ? deriveAmplitude(latestBar, prevBar?.close ?? null)
    : null
  const amplitudeText = amplitude != null ? `${amplitude.toFixed(2)}%` : '--'

  const price = quote?.price ?? null
  const prevClose = quote?.prevClose ?? null
  const { change, changePct } = deriveBarChange(
    { close: price ?? 0, changePct: quote?.changePct ?? null },
    prevClose,
  )
  const priceColor = price != null && prevClose != null
    ? changeHex(price - prevClose)
    : TEXT_TERTIARY

  const vsPrev = (v: number | null | undefined): string | undefined => {
    if (v == null || prevClose == null) return undefined
    return v >= prevClose ? riseHex() : fallHex()
  }

  const industry = stock?.industryLevel2 || stock?.industryLevel1 || stock?.industry

  const metrics: { label: string; value: string; color?: string }[] = [
    { label: '今开', value: quote?.open != null ? quote.open.toFixed(2) : '--', color: vsPrev(quote?.open) },
    { label: '最高', value: quote?.high != null ? quote.high.toFixed(2) : '--', color: vsPrev(quote?.high) },
    { label: '最低', value: quote?.low != null ? quote.low.toFixed(2) : '--', color: vsPrev(quote?.low) },
    { label: '成交量', value: formatWanShou(quote?.volume) },
    { label: '成交额', value: formatAmount(quote?.amount) },
    { label: '换手率', value: turnoverText },
    { label: '振幅', value: amplitudeText },
    { label: '总市值', value: quote?.marketCap != null ? formatAmount(quote.marketCap) : '--' },
  ]

  if ((stockLoading && !stock) || (quoteLoading && !quote)) {
    return (
      <div className="px-5 py-3">
        <Skeleton active title={false} paragraph={{ rows: 2, width: ['60%', '90%'] }} />
      </div>
    )
  }

  return (
    <div className="shrink-0">
      {/* Row1: 身份 + 现价 + 操作 */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 px-5 pt-3 pb-1.5 min-h-[48px]">
        <div className="flex items-center gap-2 min-w-0">
          <span
            className="text-[20px] font-bold leading-none whitespace-nowrap text-[#f0f1f5]"
            style={{ letterSpacing: '-0.01em' }}
          >
            {stock?.name ?? stockCode}
          </span>
          <span className="font-mono text-sm text-[#5c616e]">{stockCode}</span>
          {stock?.market && (
            <Tag className="!m-0 !text-[11px] !leading-[18px] !px-1.5 bg-[rgba(88,166,255,0.12)] !text-[#58a6ff] !border-transparent">
              {stock.market}
            </Tag>
          )}
          {industry && (
            <Tag className="!m-0 !text-[11px] !leading-[18px] !px-1.5 bg-[rgba(163,113,247,0.12)] !text-[#a371f7] !border-transparent">
              {industry}
            </Tag>
          )}
          {stock?.fullName && (
            <span className="hidden xl:inline text-[11px] text-[#5c616e] truncate max-w-[220px]">
              {stock.fullName}
            </span>
          )}
        </div>

        <div className="flex items-baseline gap-2">
          <span
            className="font-mono text-[28px] font-bold leading-none"
            style={{ color: priceColor, letterSpacing: '-0.02em' }}
          >
            {price != null ? price.toFixed(2) : '--'}
          </span>
          <span className="font-mono text-sm font-semibold leading-none" style={{ color: priceColor }}>
            {signed(change)} {signedPct(changePct)}
          </span>
        </div>

        <div className="flex items-center gap-2 ml-auto">
          <button
            type="button"
            title={isWatched ? '已在自选分组中' : '加入自选分组'}
            disabled={!stock}
            onClick={isWatched ? undefined : onAddWatchlist}
            className={`inline-flex items-center gap-1.5 px-2.5 py-[5px] text-xs rounded-md border border-[#23262d] bg-[#181a21] text-[#8a8f98] transition-colors ${
              isWatched
                ? 'cursor-default'
                : 'hover:bg-[#1c1f26] hover:border-[#2e323c] hover:text-[#f0f1f5]'
            }`}
          >
            {isWatched ? (
              <StarFilled style={{ color: '#fadb14', fontSize: 12 }} />
            ) : (
              <StarOutlined style={{ fontSize: 12 }} />
            )}
            {isWatched ? '已加入自选' : '加入自选'}
          </button>
        </div>
      </div>

      {/* Row2: 8 项快照指标 */}
      <div className="flex flex-wrap items-center px-5 pt-0.5 pb-2.5">
        {metrics.map((m, i) => (
          <div
            key={m.label}
            className={`flex items-baseline gap-1.5 ${i > 0 ? 'border-l border-[#23262d] px-[14px]' : 'pr-[14px]'}`}
          >
            <span className="text-[11px] whitespace-nowrap text-[#5c616e]">{m.label}</span>
            <span
              className="font-mono text-[13px] font-semibold whitespace-nowrap"
              style={{ color: m.color ?? TEXT_PRIMARY }}
            >
              {m.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
