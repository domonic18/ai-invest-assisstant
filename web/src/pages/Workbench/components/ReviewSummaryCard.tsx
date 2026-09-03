import { Empty, Spin, Tag } from 'antd'
import dayjs from 'dayjs'
import { Link } from 'react-router-dom'

import type { MarketReview, MarketStats } from '@ai-invest/shared'
import { MarkdownText } from '@/components/common/MarkdownText'

import { FoldCard } from './FoldCard'

interface ReviewSummaryCardProps {
  review: MarketReview | null
  stats?: MarketStats
  loading?: boolean
}

function emotionChips(stats?: MarketStats) {
  const chips: { label: string; value: string }[] = []
  if (stats?.limitUpCount != null) chips.push({ label: '涨停', value: String(stats.limitUpCount) })
  if (stats?.limitDownCount != null)
    chips.push({ label: '跌停', value: String(stats.limitDownCount) })
  if (stats?.brokenLimitCount != null)
    chips.push({ label: '炸板', value: String(stats.brokenLimitCount) })
  if (stats?.limitUpRatio != null)
    chips.push({ label: '涨停比', value: `${stats.limitUpRatio}%` })
  if (stats?.continuousRate != null)
    chips.push({ label: '连板率', value: `${(stats.continuousRate * 100).toFixed(1)}%` })
  if (stats?.emotionScore != null)
    chips.push({ label: '情绪温度', value: `${stats.emotionScore.toFixed(0)}°` })
  return chips
}

export function ReviewSummaryCard({ review, stats, loading }: ReviewSummaryCardProps) {
  const title = (
    <span>
      复盘核心结论
      {review && (
        <Tag color="purple" className="ml-2">
          {review.edited ? '人工编辑' : 'AI'} · {dayjs(review.generatedAt).format('HH:mm')} 生成
        </Tag>
      )}
    </span>
  )

  return (
    <FoldCard
      title={title}
      extra={<Link to="/review" className="text-xs">查看完整复盘</Link>}
    >
      {loading ? (
        <div className="flex justify-center py-6"><Spin /></div>
      ) : !review ? (
        <Empty
          description="今日复盘收盘后自动生成"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      ) : (
        <div>
          {review.sections.map((section) => (
            <div key={section.key} className="flex gap-2.5 py-2 border-b border-gray-800 last:border-b-0">
              <span className="shrink-0 w-14 text-[11px] font-semibold text-[#8b93e8] mt-0.5">
                {section.title}
              </span>
              <div className="text-xs text-gray-300 leading-relaxed min-w-0">
                <MarkdownText content={section.content} />
              </div>
            </div>
          ))}
          {emotionChips(stats).length > 0 && (
            <div className="flex gap-2 flex-wrap mt-3 pt-3 border-t border-gray-800">
              {emotionChips(stats).map((chip) => (
                <span
                  key={chip.label}
                  className="text-[11px] px-2.5 py-0.5 rounded-full bg-[#181a21] border border-gray-800 text-gray-400"
                >
                  {chip.label} <b className="text-gray-100 font-mono">{chip.value}</b>
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </FoldCard>
  )
}
