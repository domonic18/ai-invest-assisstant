import { Typography } from 'antd'

import { useStockSectors } from '@/hooks/useStocks'
import { changeColor, formatAmount, formatPercent } from '@/utils/formatters'
import type { StockSector } from '@ai-invest/shared'

interface StockSectorsProps {
  code: string
}

function SectorTag({ sector }: { sector: StockSector }) {
  const changeText = sector.changePct != null ? formatPercent(sector.changePct) : null
  const flowText = sector.mainNetInflow != null ? formatAmount(sector.mainNetInflow) : null

  return (
    <span
      className={`inline-flex items-center text-xs px-1.5 py-0.5 rounded ${
        sector.type === 'industry'
          ? 'bg-[#1a2a3a] text-[#6ab2ff]'
          : 'bg-[#1a2f2f] text-[#5eead4]'
      }`}
    >
      <span className="mr-1">{sector.name}</span>
      {changeText && (
        <span className={changeColor(sector.changePct)}>{changeText}</span>
      )}
      {flowText && (
        <span className={`ml-1 ${changeColor(sector.mainNetInflow)}`}>({flowText})</span>
      )}
    </span>
  )
}

export function StockSectors({ code }: StockSectorsProps) {
  const { data, isLoading } = useStockSectors(code)

  if (isLoading) {
    return (
      <div className="px-3 py-2">
        <Typography.Text type="secondary">加载板块信息...</Typography.Text>
      </div>
    )
  }

  if (!data?.sectors.length) {
    return null
  }

  const industries = data.sectors.filter((s) => s.type === 'industry')
  const concepts = data.sectors.filter((s) => s.type === 'concept')

  return (
    <div className="px-3 py-2 space-y-2">
      {industries.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-xs text-[#8c8c8c]">行业：</span>
          {industries.map((sector) => (
            <SectorTag key={`${sector.type}-${sector.name}`} sector={sector} />
          ))}
        </div>
      )}
      {concepts.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-xs text-[#8c8c8c]">概念：</span>
          {concepts.map((sector) => (
            <SectorTag key={`${sector.type}-${sector.name}`} sector={sector} />
          ))}
        </div>
      )}
    </div>
  )
}
