import { Button, Popconfirm, Tag, Tooltip } from 'antd'

import {
  ANOMALY_TYPE_LABELS,
  CATEGORY_COLORS,
  SECTOR_CATEGORY_LABELS,
  STOCK_CATEGORY_LABELS,
} from './labels'

export { SECTOR_CATEGORY_LABELS, STOCK_CATEGORY_LABELS }

export function CategoryTag({
  category,
  labels,
}: {
  category: string | null
  labels: Record<string, string>
}) {
  if (!category) {
    return (
      <Tag color="default" className="!mr-0 shrink-0">
        未归因
      </Tag>
    )
  }
  return (
    <Tag color={CATEGORY_COLORS[category] ?? 'default'} className="!mr-0 shrink-0">
      {labels[category] ?? category}
    </Tag>
  )
}

export function AnomalyTypeTags({ types }: { types: string[] }) {
  return (
    <span className="flex flex-wrap gap-1">
      {types.map((t) => (
        <Tag key={t} color="geekblue" className="!mr-0">
          {ANOMALY_TYPE_LABELS[t] ?? t}
        </Tag>
      ))}
    </span>
  )
}

/** 归因摘要单元格：分类徽标 + 单行摘要，悬停看全文。 */
export function AttributionCell({
  category,
  summary,
  labels,
}: {
  category: string | null
  summary: string | null
  labels: Record<string, string>
}) {
  if (!category && !summary) {
    return <span className="text-xs text-gray-600">未归因</span>
  }
  return (
    <Tooltip title={summary ?? undefined} placement="topLeft">
      <div className="flex items-center gap-1.5 min-w-0">
        <CategoryTag category={category} labels={labels} />
        {summary && <span className="text-xs text-gray-400 truncate">{summary}</span>}
      </div>
    </Tooltip>
  )
}

/**
 * 行级归因动作：状态感知——未归因显示「AI 归因」；
 * 已有归因的重新生成会覆盖现有结果，先弹确认，防止误触重复归因。
 */
export function AttributionAction({
  attributed,
  disabled,
  onTrigger,
}: {
  attributed: boolean
  disabled?: boolean
  onTrigger: () => void
}) {
  if (!attributed) {
    return (
      <Button
        type="link"
        size="small"
        className="!px-0"
        disabled={disabled}
        onClick={onTrigger}
      >
        AI 归因
      </Button>
    )
  }
  return (
    <Popconfirm
      title="该标的已有归因摘要"
      description="重新生成将覆盖现有结果，确定继续？"
      okText="重新归因"
      cancelText="取消"
      onConfirm={onTrigger}
    >
      <Button type="link" size="small" className="!px-0" disabled={disabled}>
        重新归因
      </Button>
    </Popconfirm>
  )
}
