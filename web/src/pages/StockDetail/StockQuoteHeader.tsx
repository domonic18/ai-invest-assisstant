import { ReloadOutlined } from '@ant-design/icons'
import { Button, Skeleton, Typography } from 'antd'

import { changeColor, formatAmount, formatNumber, formatPercent } from '@/utils/formatters'
import type { StockQuote } from '@ai-invest/shared'

interface StockQuoteHeaderProps {
  quote?: StockQuote | null
  isLoading?: boolean
  isError?: boolean
  onRetry?: () => void
}

function QuoteItem({
  label,
  value,
  className = '',
}: {
  label: string
  value: React.ReactNode
  className?: string
}) {
  return (
    <div className={`flex flex-col ${className}`}>
      <span className="text-[10px] text-[#8c8c8c]">{label}</span>
      <span className="text-xs text-[#d1d4dc] font-medium">{value}</span>
    </div>
  )
}

export function StockQuoteHeader({ quote, isLoading, isError, onRetry }: StockQuoteHeaderProps) {
  if (isLoading) {
    return (
      <div className="p-3">
        <Skeleton active paragraph={{ rows: 3 }} title={{ width: '40%' }} />
      </div>
    )
  }

  if (isError) {
    return (
      <div className="p-3 flex flex-col items-start gap-2">
        <Typography.Text type="danger" className="text-xs">
          行情加载失败
        </Typography.Text>
        {onRetry && (
          <Button size="small" icon={<ReloadOutlined />} onClick={onRetry}>
            重试
          </Button>
        )}
      </div>
    )
  }

  if (!quote) {
    return (
      <div className="h-24 flex items-center justify-center">
        <Typography.Text type="secondary" className="text-xs">
          暂无行情数据
        </Typography.Text>
      </div>
    )
  }

  const priceColor = changeColor(quote.change)

  return (
    <div className="p-3">
      <div className="flex items-baseline gap-3 mb-3">
        <span className={`text-3xl font-bold ${priceColor}`}>
          {quote.price != null ? formatNumber(quote.price) : '-'}
        </span>
        <div className="flex flex-col">
          <span className={`text-sm font-medium ${priceColor}`}>
            {quote.change != null
              ? `${quote.change >= 0 ? '+' : ''}${formatNumber(quote.change)}`
              : '-'}
          </span>
          <span className={`text-xs ${priceColor}`}>
            {quote.changePct != null ? formatPercent(quote.changePct) : '-'}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-y-2 gap-x-2">
        <QuoteItem label="今开" value={quote.open != null ? formatNumber(quote.open) : '-'} />
        <QuoteItem label="最高" value={quote.high != null ? formatNumber(quote.high) : '-'} />
        <QuoteItem label="最低" value={quote.low != null ? formatNumber(quote.low) : '-'} />
        <QuoteItem
          label="成交量"
          value={quote.volume != null ? formatAmount(quote.volume) : '-'}
        />
        <QuoteItem
          label="成交额"
          value={quote.amount != null ? formatAmount(quote.amount) : '-'}
        />
        <QuoteItem
          label="总市值"
          value={quote.marketCap != null ? formatAmount(quote.marketCap) : '-'}
        />
      </div>
    </div>
  )
}
