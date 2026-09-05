import { DownOutlined, ReloadOutlined, UpOutlined } from '@ant-design/icons'
import { Button, Skeleton } from 'antd'
import { useState } from 'react'

import type { Stock, StockSector } from '@ai-invest/shared'

interface StockSectorsProps {
  sectors?: { code: string; name: string; sectors: StockSector[] } | null
  stock?: Stock | null
  isLoading?: boolean
  isError?: boolean
  onRetry?: () => void
}

/** 收起态展示的概念数量：覆盖高频关注即可，避免标签占满侧栏。 */
const COLLAPSED_COUNT = 5

function SectionHeader({ title, sub }: { title: string; sub?: string }) {
  return (
    <div className="flex items-center justify-between px-3.5 py-2.5 border-b border-[#23262d]">
      <span className="text-[13px] font-semibold text-[#f0f1f5]">{title}</span>
      {sub && <span className="text-[11px] text-[#5c616e]">{sub}</span>}
    </div>
  )
}

export function StockSectors({
  sectors,
  stock,
  isLoading,
  isError,
  onRetry,
}: StockSectorsProps) {
  const [expanded, setExpanded] = useState(false)

  if (isLoading) {
    return (
      <div>
        <SectionHeader title="所属行业" sub="申万分类" />
        <div className="px-3.5 py-3">
          <Skeleton active title={false} paragraph={{ rows: 2 }} />
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div>
        <SectionHeader title="所属行业" sub="申万分类" />
        <div className="px-3.5 py-3 flex items-center gap-2">
          <span className="text-xs text-[#f85149]">概念板块加载失败</span>
          {onRetry && (
            <Button size="small" icon={<ReloadOutlined />} onClick={onRetry}>
              重试
            </Button>
          )}
        </div>
      </div>
    )
  }

  const industryLevels = [
    { label: '一级', value: stock?.industryLevel1 },
    { label: '二级', value: stock?.industryLevel2 },
    { label: '三级', value: stock?.industryLevel3 },
  ].filter((lv): lv is { label: string; value: string } => Boolean(lv.value))

  const concepts = sectors?.sectors.filter((s) => s.type === 'concept') ?? []
  if (!industryLevels.length && !concepts.length) return null

  // 有板块资金流的概念排前（按主力净流入降序）作为"最相关"排序，其余保持原始顺序。
  const ranked = [
    ...concepts
      .filter((c) => c.mainNetInflow != null)
      .sort((a, b) => (b.mainNetInflow ?? 0) - (a.mainNetInflow ?? 0)),
    ...concepts.filter((c) => c.mainNetInflow == null),
  ]
  const visible = expanded ? ranked : ranked.slice(0, COLLAPSED_COUNT)
  const hiddenCount = ranked.length - COLLAPSED_COUNT

  return (
    <div>
      {industryLevels.length > 0 && (
        <div>
          <SectionHeader title="所属行业" sub="申万分类" />
          <div className="px-3.5 pb-1">
            {industryLevels.map((lv, i) => (
              <div
                key={lv.label}
                className={`flex items-center gap-3 py-[7px] ${
                  i < industryLevels.length - 1 ? 'border-b border-[#23262d]' : ''
                }`}
              >
                <span className="shrink-0 w-8 text-[11px] text-[#5c616e]">{lv.label}</span>
                <span className="text-[13px] text-[#f0f1f5]">{lv.value}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      {concepts.length > 0 && (
        <div>
          <SectionHeader
            title="概念归属"
            sub={`按主力净流入排序 · 共 ${concepts.length} 个`}
          />
          <div className="px-3.5 pb-3 pt-2.5">
            <div className="flex flex-wrap gap-1.5">
              {visible.map((sector) => (
                <span
                  key={`${sector.type}-${sector.name}`}
                  className="inline-flex items-center rounded-full px-2.5 py-1 text-xs bg-[#181a21] border border-[#23262d] text-[#8a8f98]"
                >
                  {sector.name}
                </span>
              ))}
            </div>
            {(hiddenCount > 0 || expanded) && (
              <button
                type="button"
                onClick={() => setExpanded((prev) => !prev)}
                className="mt-2 w-full flex items-center justify-center gap-1 py-[5px] text-xs text-[#5c616e] bg-transparent border border-dashed border-[#23262d] rounded transition-colors hover:text-[#5e6ad2] hover:border-[rgba(94,106,210,0.4)]"
              >
                {expanded ? (
                  <>
                    收起 <UpOutlined className="!text-[10px]" />
                  </>
                ) : (
                  <>
                    展开全部 {hiddenCount} 个 <DownOutlined className="!text-[10px]" />
                  </>
                )}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
