import { Empty, Spin, Tag } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { useMemo } from 'react'

import type { SectorFundFlow } from '@ai-invest/shared'

import { fetchHotspots } from '@/api/hotspot'
import { changeColor } from '@/utils/formatters'

import { formatAmount } from '../utils'

// 信号卡取最新交易日 |主力净流入| 前 8 的板块（原型右栏规格）
const SIGNAL_LIMIT = 8

function pickSignals(items: SectorFundFlow[]): {
  tradeDate: string | null
  rows: SectorFundFlow[]
} {
  if (!items.length) return { tradeDate: null, rows: [] }
  const tradeDate = items
    .map((it) => it.tradeDate)
    .reduce((a, b) => (b > a ? b : a))
  const rows = items
    .filter((it) => it.tradeDate === tradeDate && it.mainNetInflow !== null)
    .sort((a, b) => Math.abs(b.mainNetInflow ?? 0) - Math.abs(a.mainNetInflow ?? 0))
    .slice(0, SIGNAL_LIMIT)
  return { tradeDate, rows }
}

/** 资金异动信号：最新交易日主力净流入/流出幅度最大的板块（流入红 · 流出绿）。 */
export function FundSignalCard() {
  const { data, isLoading } = useQuery({
    queryKey: ['hotspot', 'signals'],
    queryFn: () => fetchHotspots({ page: 1, pageSize: 200 }),
  })
  const { tradeDate, rows } = useMemo(() => pickSignals(data?.items ?? []), [data])

  if (isLoading) {
    return <div className="flex justify-center py-16"><Spin /></div>
  }
  if (!rows.length) {
    return <Empty description="暂无资金信号" image={Empty.PRESENTED_IMAGE_SIMPLE} />
  }
  return (
    <div>
      {rows.map((row) => {
        const inflow = (row.mainNetInflow ?? 0) > 0
        return (
          <div
            key={`${row.sectorCode}-${row.sectorType}`}
            className="flex items-center gap-3 py-2 border-b border-dashed border-gray-800 last:border-b-0"
          >
            <div className="min-w-0 flex-1">
              <div className="truncate text-[13px] text-gray-100">{row.sectorName}</div>
              {row.topStockName && (
                <div className="truncate text-[11px] text-gray-500">
                  领涨: {row.topStockName}
                </div>
              )}
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span className={`text-[13px] font-mono font-semibold ${changeColor(row.mainNetInflow)}`}>
                {formatAmount(row.mainNetInflow)}
              </span>
              <Tag color={inflow ? 'red' : 'green'} className="!mr-0">
                {inflow ? '净流入' : '净流出'}
              </Tag>
            </div>
          </div>
        )
      })}
      <div className="pt-2.5 text-[10px] text-gray-600 border-t border-dashed border-gray-800">
        {tradeDate ? `${tradeDate} · ` : ''}按主力净流入绝对值排序，完整明细见下方板块资金明细
      </div>
    </div>
  )
}
