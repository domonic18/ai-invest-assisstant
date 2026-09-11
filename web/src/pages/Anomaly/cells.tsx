import { Tag, Tooltip } from 'antd'

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
