import { ReloadOutlined } from '@ant-design/icons'
import { Button, Skeleton, Typography } from 'antd'

import { changeColor, formatAmount, formatPercent } from '@/utils/formatters'
import type { StockSector } from '@ai-invest/shared'

interface StockSectorsProps {
  sectors?: { code: string; name: string; sectors: StockSector[] } | null
  isLoading?: boolean
  isError?: boolean
  onRetry?: () => void
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

export function StockSectors({ sectors, isLoading, isError, onRetry }: StockSectorsProps) {
  if (isLoading) {
    return (
      <div className="px-3 py-2">
        <Skeleton active paragraph={{ rows: 2 }} />
      </div>
    )
  }

  if (isError) {
    return (
      <div className="px-3 py-2 flex items-center gap-2">
        <Typography.Text type="danger" className="text-xs">
          板块信息加载失败
        </Typography.Text>
        {onRetry && (
          <Button size="small" icon={<ReloadOutlined />} onClick={onRetry}>
            重试
          </Button>
        )}
      </div>
    )
  }

  if (!sectors?.sectors.length) {
    return null
  }

  const industries = sectors.sectors.filter((s) => s.type === 'industry')
  const concepts = sectors.sectors.filter((s) => s.type === 'concept')

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
