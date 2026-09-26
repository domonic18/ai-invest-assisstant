/**
 * 底部时间轴：每个 Agent 一行——「正在做」近期活动（计划/复盘）与
 * 「接下来」下次任务时刻（后端按 cron + 交易日历算好的 UTC 时刻）。
 */
import { Card, Empty, Spin, Typography } from 'antd'
import dayjs from 'dayjs'

import type { AgentOverviewItem } from '@ai-invest/shared'

import { formatRelativeTime } from '@/utils/formatters'

function AgentTimelineRow({ item }: { item: AgentOverviewItem }) {
  const latest = item.recentActivity[0]
  const done = item.recentActivity.slice(0, 3)

  return (
    <div className="grid gap-2 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 md:grid-cols-[10rem_1fr_16rem]">
      <div className="flex items-center gap-2">
        <span
          className="inline-block size-2 rounded-full"
          style={{ backgroundColor: item.profile.accentColor }}
        />
        <Typography.Text strong className="text-xs">
          {item.profile.name}
        </Typography.Text>
      </div>
      <div className="min-w-0">
        <Typography.Text type="secondary" className="text-xs">
          正在做
        </Typography.Text>
        {latest ? (
          <div className="flex min-w-0 items-baseline gap-2">
            <Typography.Text className="truncate text-xs">{latest.title}</Typography.Text>
            {latest.occurredAt && (
              <Typography.Text type="secondary" className="shrink-0 text-xs">
                {formatRelativeTime(latest.occurredAt)}
              </Typography.Text>
            )}
          </div>
        ) : (
          <Typography.Text type="secondary" className="text-xs">
            暂无活动记录
          </Typography.Text>
        )}
        {done.length > 1 && (
          <Typography.Paragraph type="secondary" className="!mb-0 truncate text-xs !mt-0.5">
            {done
              .slice(1)
              .map((activity) => activity.title)
              .join(' · ')}
          </Typography.Paragraph>
        )}
      </div>
      <div className="min-w-0">
        <Typography.Text type="secondary" className="text-xs">
          接下来
        </Typography.Text>
        {item.nextTasks.length > 0 ? (
          <div className="space-y-0.5">
            {item.nextTasks.map((task) => (
              <div key={task.task} className="flex items-baseline gap-2">
                <Typography.Text className="truncate text-xs">{task.task}</Typography.Text>
                <Typography.Text type="secondary" className="shrink-0 text-xs">
                  {dayjs(task.scheduledAt).format('HH:mm')}
                </Typography.Text>
              </div>
            ))}
          </div>
        ) : (
          <Typography.Text type="secondary" className="text-xs">
            未启用定时任务
          </Typography.Text>
        )}
      </div>
    </div>
  )
}

export function ActivityTimeline({
  items,
  isLoading,
  generatedAt,
}: {
  items: AgentOverviewItem[]
  isLoading: boolean
  generatedAt?: string
}) {
  return (
    <Card
      size="small"
      title="活动时间轴"
      extra={
        generatedAt ? (
          <Typography.Text type="secondary" className="text-xs">
            聚合于 {dayjs(generatedAt).format('HH:mm:ss')}
          </Typography.Text>
        ) : null
      }
      className="shrink-0"
    >
      {isLoading ? (
        <div className="flex justify-center py-4">
          <Spin size="small" />
        </div>
      ) : items.length === 0 ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无注册 Agent" />
      ) : (
        <div className="space-y-2">
          {items.map((item) => (
            <AgentTimelineRow key={item.profile.agentKey} item={item} />
          ))}
        </div>
      )}
    </Card>
  )
}
