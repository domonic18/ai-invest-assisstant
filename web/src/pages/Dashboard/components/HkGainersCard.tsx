import { Card, Skeleton } from 'antd'
import { Link } from 'react-router-dom'

import type { HkGainer } from '@ai-invest/shared'
import { SourceNote } from '@/components/common/SourceNote'
import { useColorScheme } from '@/stores/settings'
import { changeHex, formatAmount, formatPercent } from '@/utils/formatters'

interface HkGainersCardProps {
  data?: HkGainer[]
  loading: boolean
}

/** 港股涨幅榜：日 K 收盘口径（非实时），流动性门槛过滤后按涨跌幅降序。 */
export function HkGainersCard({ data, loading }: HkGainersCardProps) {
  useColorScheme()

  if (loading) {
    return <Skeleton active paragraph={{ rows: 4 }} />
  }

  return (
    <Card
      variant="borderless"
      title="港股涨幅榜"
      extra={<span className="text-xs text-gray-500">数据日期 {data?.[0]?.tradeDate ?? '-'}</span>}
    >
      {!data || data.length === 0 ? (
        <div className="text-gray-500 text-sm">
          港股休市或当日数据未采集（A/H 假日不一致，港股收盘约 16:10 后更新）
        </div>
      ) : (
        <div className="space-y-1.5">
          {data.map((item, i) => (
            <div
              key={item.stockCode}
              className="flex items-center gap-3 rounded px-2 py-1.5 bg-[#1a1d24]"
            >
              <span className="w-5 shrink-0 text-center text-xs font-mono text-gray-500">
                {i + 1}
              </span>
              <Link to={`/stock/${item.stockCode}`} className="flex-1 font-medium truncate hover:underline">
                {item.stockName}
              </Link>
              <span className="hidden sm:inline font-mono text-xs text-gray-500">{item.stockCode}</span>
              <span className="font-mono text-sm shrink-0">{item.close?.toFixed(2) ?? '-'}</span>
              <span
                className="text-sm font-medium shrink-0 w-16 text-right"
                style={{ color: changeHex(item.changePct) }}
              >
                {item.changePct != null ? formatPercent(item.changePct) : '-'}
              </span>
              <span className="hidden md:inline font-mono text-xs text-gray-500 w-20 text-right shrink-0">
                {formatAmount(item.amount)}
              </span>
            </div>
          ))}
        </div>
      )}
      <SourceNote>
        东方财富 · 港股日 K 前复权 · 行情延时 15 分钟 · 门槛：收盘 ≥0.5 港元且成交额 ≥1000 万港元
      </SourceNote>
    </Card>
  )
}
