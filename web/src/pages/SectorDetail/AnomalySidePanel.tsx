import { DoubleLeftOutlined, DoubleRightOutlined } from '@ant-design/icons'
import { Empty, Tag, Tooltip, Typography } from 'antd'

import type { ApiSectorAnomalyDay } from '@ai-invest/shared'

import { ANOMALY_TYPE_LABELS } from '../Anomaly/labels'
import { AttributionCell, SECTOR_CATEGORY_LABELS } from '../Anomaly/cells'

interface AnomalySidePanelProps {
  anomalyDays: ApiSectorAnomalyDay[]
  collapsed: boolean
  onToggleCollapsed: () => void
}

function AnomalyItem({ day }: { day: ApiSectorAnomalyDay }) {
  return (
    <div className="px-3 py-2.5 border-b border-[#23262d] last:border-b-0">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-mono text-gray-300">{day.tradeDate}</span>
        <Tooltip title="异动强度（多维度加权 0-100）">
          <span className="font-mono text-xs font-semibold text-[#5e6ad2]">
            {day.strength}
          </span>
        </Tooltip>
      </div>
      <div className="flex flex-wrap gap-1 mt-1.5">
        {(day.anomalyTypes ?? []).map((t) => (
          <Tag key={t} color="geekblue" className="!text-[10px] !leading-4 !px-1.5 !mr-0">
            {ANOMALY_TYPE_LABELS[t] ?? t}
          </Tag>
        ))}
      </div>
      <div className="mt-1.5">
        <AttributionCell
          category={day.attributionCategory}
          summary={day.attributionSummary}
          labels={SECTOR_CATEGORY_LABELS}
        />
      </div>
    </div>
  )
}

/** 板块详情右侧异动栏：近 30 日异动日 + AI 归因，收起为窄条。 */
export function AnomalySidePanel({
  anomalyDays,
  collapsed,
  onToggleCollapsed,
}: AnomalySidePanelProps) {
  const days = [...anomalyDays].sort((a, b) => b.tradeDate.localeCompare(a.tradeDate))

  if (collapsed) {
    return (
      <div
        className="flex flex-col items-center gap-3 shrink-0 py-2 rounded border border-[#23262d]"
        style={{ backgroundColor: '#0b0d12', width: 36 }}
      >
        <button
          type="button"
          title="展开异动栏"
          onClick={onToggleCollapsed}
          className="flex items-center justify-center w-6 h-6 rounded text-[#8a8f98] transition-colors hover:bg-[#1c1f26] hover:text-[#f0f1f5]"
        >
          <DoubleLeftOutlined className="!text-[11px]" />
        </button>
        <div
          className="text-[11px] text-[#8a8f98] whitespace-nowrap"
          style={{ writingMode: 'vertical-rl' }}
        >
          异动 {days.length}
        </div>
      </div>
    )
  }

  return (
    <div
      className="flex flex-col shrink-0 rounded border border-[#23262d] overflow-hidden w-full lg:w-[320px]"
      style={{ backgroundColor: '#0b0d12', maxHeight: 640 }}
    >
      <div
        className="flex items-center justify-between px-3 shrink-0"
        style={{ height: 38, borderBottom: '1px solid #23262d' }}
      >
        <Typography.Text className="text-xs font-semibold text-gray-200">
          近期异动
          <span className="ml-1.5 font-mono text-[10px] text-[#8a8f98]">
            {days.length} 条
          </span>
        </Typography.Text>
        <button
          type="button"
          title="收起异动栏"
          onClick={onToggleCollapsed}
          className="flex items-center justify-center w-6 h-6 rounded text-[#8a8f98] transition-colors hover:bg-[#1c1f26] hover:text-[#f0f1f5]"
        >
          <DoubleRightOutlined className="!text-[11px]" />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto min-h-0">
        {days.length === 0 ? (
          <div className="flex items-center justify-center h-40">
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="近 30 日无异动记录" />
          </div>
        ) : (
          days.map((day) => <AnomalyItem key={day.tradeDate} day={day} />)
        )}
      </div>
    </div>
  )
}
