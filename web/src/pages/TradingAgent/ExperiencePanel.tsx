/**
 * Agent 经验总结（模拟管理页 tab）：聚合日/周/月三期复盘提取的经验条目。
 *
 * 数据源与复盘记录同源（admin GET /trading-agent/review），404 视为该周期
 * 尚未生成；批次 9 落 agent_memory 后此处切换为记忆库读取。
 */
import { Alert, Card, Empty, Skeleton, Tag, Typography } from 'antd'

import type {
  ApiTradingAgentReviewExperience,
  TradingReviewPeriod,
} from '@ai-invest/shared'

import { useTradingAgentReview } from '@/hooks/useTradingAgent'

const MEM_TYPE_META: Record<
  ApiTradingAgentReviewExperience['memType'],
  { label: string; color: string }
> = {
  discipline: { label: '纪律', color: 'gold' },
  method: { label: '方法', color: 'processing' },
  lesson: { label: '教训', color: 'error' },
}

const PERIOD_META: Record<TradingReviewPeriod, { label: string }> = {
  day: { label: '日复盘' },
  week: { label: '周复盘' },
  month: { label: '月复盘' },
}

interface ExperienceEntry extends ApiTradingAgentReviewExperience {
  period: TradingReviewPeriod
  tradeDate: string
}

function useAllExperiences() {
  const day = useTradingAgentReview('day')
  const week = useTradingAgentReview('week')
  const month = useTradingAgentReview('month')
  const queries = [
    { period: 'day' as const, query: day },
    { period: 'week' as const, query: week },
    { period: 'month' as const, query: month },
  ]
  const entries: ExperienceEntry[] = []
  for (const { period, query } of queries) {
    const review = query.data
    if (!review) continue
    for (const exp of review.experiences) {
      entries.push({ ...exp, period, tradeDate: review.tradeDate })
    }
  }
  const loading = queries.some(({ query }) => query.isLoading)
  return { entries, loading }
}

function ExperienceItem({ entry }: { entry: ExperienceEntry }) {
  const memType = MEM_TYPE_META[entry.memType] ?? { label: entry.memType, color: 'default' }
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <Tag color={memType.color} className="!mr-0">
          {memType.label}
        </Tag>
        <Typography.Text strong className="text-sm">
          {entry.title}
        </Typography.Text>
        <span className="ml-auto text-xs text-white/40">
          {PERIOD_META[entry.period].label} · {entry.tradeDate}
        </span>
      </div>
      <Typography.Paragraph className="!mb-0 mt-1 text-xs text-white/60">
        {entry.body}
      </Typography.Paragraph>
    </div>
  )
}

export function ExperiencePanel() {
  const { entries, loading } = useAllExperiences()

  return (
    <Card size="small" title="经验总结">
      <Alert
        type="info"
        showIcon
        className="!mb-3"
        message="复盘后自动提取的经验条目，每日计划生成时会注入 Agent 作为决策参考；后续版本支持人工增删与停用。"
      />
      {loading ? (
        <Skeleton active paragraph={{ rows: 4 }} />
      ) : entries.length === 0 ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="暂无经验总结（盘后复盘生成后自动提取）"
        />
      ) : (
        <div className="space-y-2">
          {entries.map((entry) => (
            <ExperienceItem key={`${entry.period}-${entry.tradeDate}-${entry.title}`} entry={entry} />
          ))}
        </div>
      )}
    </Card>
  )
}
