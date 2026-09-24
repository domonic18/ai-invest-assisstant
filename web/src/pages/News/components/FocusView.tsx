import { DownOutlined, UpOutlined } from '@ant-design/icons'
import { Button, Card, Empty, Spin, Tag, theme, Timeline, Tooltip, Typography } from 'antd'
import dayjs from 'dayjs'
import { useState } from 'react'

import type {
  ApiFocusItem,
  ApiScoreFactors,
  ApiStoryline,
  ApiStorylineStatus,
} from '@ai-invest/shared'

import { useNewsFocus, useStopNewsStory } from '@/hooks/useNewsFocus'
import { formatDateTime } from '@/utils/formatters'

/** 故事线状态 → Tag 颜色/文案。 */
const STATUS_META: Record<ApiStorylineStatus, { color: string; label: string }> = {
  tracking: { color: 'processing', label: '跟踪中' },
  near_end: { color: 'warning', label: '临近尾声' },
  finished: { color: 'default', label: '已完结' },
}

/** 评分构成三维横条（存量评分行无构成为 null → 显示「—」）。 */
function FactorsBar({ factors }: { factors: ApiScoreFactors | null }) {
  const { token } = theme.useToken()
  if (!factors) {
    return (
      <Tooltip title="历史评分无构成数据">
        <span className="text-xs opacity-50">构成 —</span>
      </Tooltip>
    )
  }
  const rows = [
    { label: '影响范围', value: factors.impactScope },
    { label: '确定性', value: factors.certainty },
    { label: '关联标的', value: factors.relatedCount },
  ]
  return (
    <div className="space-y-1 w-56">
      {rows.map((row) => (
        <div key={row.label} className="flex items-center gap-2">
          <span className="text-xs opacity-60 w-14 shrink-0 text-right">
            {row.label}
          </span>
          <div className="h-1 flex-1 bg-white/10 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full"
              style={{
                width: `${Math.min(100, Math.max(0, row.value))}%`,
                background: token.colorPrimary,
              }}
            />
          </div>
          <span className="text-xs font-mono w-7 shrink-0 text-right">
            {row.value}
          </span>
        </div>
      ))}
    </div>
  )
}

/** 今日重点条目：分值 + 构成三维 + 理由。 */
function HighlightItem({ item }: { item: ApiFocusItem }) {
  return (
    <div className="flex gap-3 py-3 border-b border-white/5">
      <div className="shrink-0 w-12 text-center">
        <div className="text-xl font-bold font-mono text-red-400">
          {item.score}
        </div>
        <div className="text-[10px] opacity-50">重要度</div>
      </div>
      <div className="flex-1 min-w-0 space-y-1">
        <div className="flex items-center gap-2 flex-wrap">
          {item.title && (
            <span className="text-sm font-semibold">{item.title}</span>
          )}
          <span className="text-xs opacity-50">
            {dayjs(item.publishTime).format('HH:mm')}
          </span>
        </div>
        {item.content && (
          <Typography.Paragraph
            className="!mb-0"
            ellipsis={{ rows: 2, expandable: true, symbol: '展开' }}
          >
            {item.content}
          </Typography.Paragraph>
        )}
        {item.reason && (
          <div className="text-xs opacity-60">评分理由：{item.reason}</div>
        )}
      </div>
      <div className="shrink-0 self-center">
        <FactorsBar factors={item.factors} />
      </div>
    </div>
  )
}

/** 故事线卡：状态/来源标注 + 报道数与时间跨度 + 节点链展开。 */
function StorylineCard({ line }: { line: ApiStoryline }) {
  const [expanded, setExpanded] = useState(false)
  const stopStory = useStopNewsStory()
  const status = STATUS_META[line.status]
  const spanText = `${dayjs(line.firstSeenAt).format('M月D日 HH:mm')} ~ ${dayjs(
    line.lastSeenAt,
  ).format('M月D日 HH:mm')}`

  return (
    <Card size="small" className="!bg-white/[0.03]">
      <div className="space-y-2">
        <div className="flex items-center gap-2 flex-wrap">
          <Tag color={status.color}>{status.label}</Tag>
          <span className="text-sm font-semibold">{line.title}</span>
          <Tag className="!m-0 !text-xs">
            {line.origin === 'ai' ? 'AI 自动建线' : '手动跟踪'}
          </Tag>
        </div>
        {line.summary && <div className="text-xs opacity-70">{line.summary}</div>}
        <div className="flex items-center gap-4 flex-wrap text-xs opacity-60">
          <span>{line.reportCount} 篇报道</span>
          <span>{spanText}</span>
        </div>
        {line.latestBrief && (
          <div className="text-sm">
            <span className="opacity-50">最新进展：</span>
            {line.latestBrief}
          </div>
        )}
        <div className="flex items-center justify-between">
          <Button
            type="link"
            size="small"
            className="!px-0"
            onClick={() => setExpanded((v) => !v)}
          >
            节点链（{line.nodes.length}）
            {expanded ? <UpOutlined /> : <DownOutlined />}
          </Button>
          <Button
            size="small"
            loading={stopStory.isPending && stopStory.variables === line.id}
            onClick={() => stopStory.mutate(line.id)}
          >
            停止跟踪
          </Button>
        </div>
        {expanded && line.nodes.length > 0 && (
          <Timeline
            className="!mt-2 !mb-0"
            items={line.nodes.map((node) => ({
              children: (
                 <div className="text-xs">
                   <span className="opacity-50">{formatDateTime(node.time)}</span>
                   <div>{node.brief}</div>
                 </div>
              ),
            }))}
          />
        )}
      </div>
    </Card>
  )
}

/** 重点与跟踪视图：今日重点 TOP（评分构成透明）+ 故事线聚合跟踪。 */
export function FocusView() {
  const { data, isLoading } = useNewsFocus()

  if (isLoading) {
    return (
      <div className="py-16 flex justify-center">
        <Spin />
      </div>
    )
  }
  const highlights = data?.highlights ?? []
  const storylines = data?.storylines ?? []
  if (highlights.length === 0 && storylines.length === 0) {
    return (
      <Card variant="borderless">
        <Empty description="暂无重点资讯与跟踪中的故事线" />
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      {highlights.length > 0 && (
        <Card
          variant="borderless"
          title={`今日重点（≥70 分 · ${highlights.length} 条）`}
        >
          {highlights.map((item) => (
            <HighlightItem key={`${item.source}:${item.itemId}`} item={item} />
          ))}
        </Card>
      )}
      {storylines.length > 0 && (
        <div className="space-y-3">
          <Typography.Text className="text-sm font-semibold">
            事件故事线（{storylines.length} 条）
          </Typography.Text>
          {storylines.map((line) => (
            <StorylineCard key={line.id} line={line} />
          ))}
        </div>
      )}
    </div>
  )
}
