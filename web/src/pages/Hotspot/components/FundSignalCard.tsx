import { Empty, Spin, Tag } from 'antd'
import { useMemo } from 'react'

import type { SectorFundFlow } from '@ai-invest/shared'

import { useLatestDaySectors } from '@/hooks/useHotspot'
import { formatAmount } from '@/utils/formatters'

// 信号卡取最新交易日 |主力净流入| 前 8 的板块（原型右栏规格）
const SIGNAL_LIMIT = 8
// 大幅流入阈值（元）：≥30 亿为大幅流入，其余流入记持续流入
const HEAVY_INFLOW_YUAN = 30e8

function pickSignals(items: SectorFundFlow[]): SectorFundFlow[] {
  return items
    .filter((it) => it.mainNetInflow !== null)
    .sort((a, b) => Math.abs(b.mainNetInflow ?? 0) - Math.abs(a.mainNetInflow ?? 0))
    .slice(0, SIGNAL_LIMIT)
}

function signalTier(value: number): { color: string; label: string } {
  if (value <= 0) return { color: 'green', label: '资金流出' }
  if (value >= HEAVY_INFLOW_YUAN) return { color: 'red', label: '大幅流入' }
  return { color: 'gold', label: '持续流入' }
}

/** 资金异动信号：最新交易日主力净流入/流出幅度最大的板块（原型分级标签 + 亿口径）。 */
export function FundSignalCard() {
  const { data, isLoading } = useLatestDaySectors()
  const rows = useMemo(() => pickSignals(data ?? []), [data])

  if (isLoading) {
    return <div className="flex justify-center py-16"><Spin /></div>
  }
  if (!rows.length) {
    return <Empty description="暂无资金信号" image={Empty.PRESENTED_IMAGE_SIMPLE} />
  }
  const tradeDate = rows[0].tradeDate
  return (
    <div>
      {rows.map((row) => {
        const inflow = (row.mainNetInflow ?? 0) > 0
        const tier = signalTier(row.mainNetInflow ?? 0)
        return (
          <div
            key={`${row.sectorCode}-${row.sectorType}`}
            className="flex items-center justify-between gap-3 border-b border-dashed border-gray-800 py-2.5 last:border-b-0"
          >
            <div className="min-w-0">
              <div className="truncate text-[13px] font-medium text-gray-100">
                {row.sectorName}
              </div>
              <div className="text-[11px] text-gray-500">
                主力净{inflow ? '流入' : '流出'} {formatAmount(Math.abs(row.mainNetInflow ?? 0))}
              </div>
            </div>
            <Tag color={tier.color} className="!mr-0 shrink-0">
              {tier.label}
            </Tag>
          </div>
        )
      })}
      <div className="border-t border-dashed border-gray-800 pt-2.5 text-[10px] text-gray-600">
        {tradeDate ? `${tradeDate} · ` : ''}按主力净流入绝对值排序，完整明细见下方板块资金明细
      </div>
    </div>
  )
}
