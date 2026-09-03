import { Card, Empty, Spin, Tag } from 'antd'
import { Link } from 'react-router-dom'

import type { MarketReview } from '@ai-invest/shared'
import { MarkdownText } from '@/components/common/MarkdownText'

interface ReviewSummaryCardProps {
  review: MarketReview | null
  loading?: boolean
}

export function ReviewSummaryCard({ review, loading }: ReviewSummaryCardProps) {
  return (
    <Card
      variant="borderless"
      title="AI 复盘速览"
      extra={<Link to="/review" className="text-xs">完整复盘</Link>}
    >
      {loading ? (
        <div className="flex justify-center py-6"><Spin /></div>
      ) : !review ? (
        <Empty
          description="今日复盘收盘后自动生成"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      ) : (
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <span>交易日 {review.tradeDate}</span>
            {review.edited ? <Tag color="orange">已编辑</Tag> : <Tag color="purple">AI 生成</Tag>}
          </div>
          {review.sections.map((section) => (
            <div key={section.key}>
              <div className="text-sm font-medium mb-1">{section.title}</div>
              <div className="text-sm">
                <MarkdownText content={section.content} />
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}
