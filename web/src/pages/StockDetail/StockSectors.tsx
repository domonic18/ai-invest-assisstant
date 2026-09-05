import { DownOutlined, ReloadOutlined, UpOutlined } from '@ant-design/icons'
import { Button, Skeleton, Typography } from 'antd'
import { useState } from 'react'

import { changeColor, formatAmount, formatPercent } from '@/utils/formatters'
import type { StockSector } from '@ai-invest/shared'

interface StockSectorsProps {
  sectors?: { code: string; name: string; sectors: StockSector[] } | null
  isLoading?: boolean
  isError?: boolean
  onRetry?: () => void
}

/** 收起态展示的概念数量：覆盖高频关注即可，避免标签占满侧栏。 */
const COLLAPSED_COUNT = 5

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
  const [expanded, setExpanded] = useState(false)

  if (isLoading) {
    return (
      <div className="px-3 py-2">
        <Skeleton active paragraph={{ rows: 1 }} />
      </div>
    )
  }

  if (isError) {
    return (
      <div className="px-3 py-2 flex items-center gap-2">
        <Typography.Text type="danger" className="text-xs">
          概念板块加载失败
        </Typography.Text>
        {onRetry && (
          <Button size="small" icon={<ReloadOutlined />} onClick={onRetry}>
            重试
          </Button>
        )}
      </div>
    )
  }

  const concepts = sectors?.sectors.filter((s) => s.type === 'concept') ?? []
  if (!concepts.length) return null

  // 行业归属已在头部展示；此处只列概念。有板块资金流的概念排前
  // （按主力净流入降序）作为"最相关"排序，其余保持原始顺序。
  const ranked = [
    ...concepts
      .filter((c) => c.mainNetInflow != null)
      .sort((a, b) => (b.mainNetInflow ?? 0) - (a.mainNetInflow ?? 0)),
    ...concepts.filter((c) => c.mainNetInflow == null),
  ]
  const visible = expanded ? ranked : ranked.slice(0, COLLAPSED_COUNT)
  const hiddenCount = ranked.length - COLLAPSED_COUNT

  return (
    <div className="px-3 py-2">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-xs text-[#8c8c8c]">概念：</span>
        {visible.map((sector) => (
          <SectorTag key={`${sector.type}-${sector.name}`} sector={sector} />
        ))}
        {hiddenCount > 0 && !expanded && (
          <Button
            type="link"
            size="small"
            className="!px-0 !h-auto !text-xs"
            icon={<DownOutlined className="!text-[10px]" />}
            onClick={() => setExpanded(true)}
          >
            展开 {hiddenCount} 个
          </Button>
        )}
        {expanded && hiddenCount > 0 && (
          <Button
            type="link"
            size="small"
            className="!px-0 !h-auto !text-xs"
            icon={<UpOutlined className="!text-[10px]" />}
            onClick={() => setExpanded(false)}
          >
            收起
          </Button>
        )}
      </div>
    </div>
  )
}
