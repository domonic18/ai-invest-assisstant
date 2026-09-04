import { Empty, Spin } from 'antd'
import { Link } from 'react-router-dom'

import type { WorkbenchSectorFlowItem } from '@ai-invest/shared'

import { useColorScheme } from '@/stores/settings'
import { changeColor } from '@/utils/formatters'

import { FoldCard } from './FoldCard'

interface SectorFlowCardProps {
  items?: WorkbenchSectorFlowItem[]
  loading?: boolean
}

function formatPct(value: number | null): string {
  if (value === null) return '-'
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`
}

function formatInflow(value: number | null): string {
  if (value === null) return '-'
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}亿`
}

/** 板块资金动向卡：最新交易日行业板块主力净流入排行，完整视图在资金流向页。 */
export function SectorFlowCard({ items, loading }: SectorFlowCardProps) {
  useColorScheme()

  return (
    <FoldCard
      title="板块资金动向"
      extra={<Link to="/capital-flow" className="text-xs">查看资金流向 →</Link>}
    >
      {loading ? (
        <div className="flex justify-center py-6"><Spin /></div>
      ) : items?.length ? (
        items.map((item) => (
          <div
            key={item.sectorName}
            className="flex items-center gap-3 py-2 text-xs border-b border-gray-800 last:border-b-0"
          >
            <div className="min-w-0 flex-1">
              <div className="truncate text-gray-100">{item.sectorName}</div>
              {item.topStockName && (
                <div className="truncate text-[11px] text-gray-500">
                  领涨: {item.topStockName}
                </div>
              )}
            </div>
            <span
              className={`w-16 shrink-0 text-right font-mono ${changeColor(item.changePct)}`}
            >
              {formatPct(item.changePct)}
            </span>
            <span
              className={`w-20 shrink-0 text-right font-mono ${changeColor(item.mainNetInflow)}`}
            >
              {formatInflow(item.mainNetInflow)}
            </span>
          </div>
        ))
      ) : (
        <Empty
          description="暂无板块资金数据"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      )}
    </FoldCard>
  )
}
