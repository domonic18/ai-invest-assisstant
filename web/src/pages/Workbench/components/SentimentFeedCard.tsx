import { Empty, Spin } from 'antd'
import { Link } from 'react-router-dom'

import { SentimentCard } from '@/pages/News/components/Sentiment/SentimentCard'
import { SENTIMENT_REFETCH_INTERVAL, useSentimentFeed } from '@/hooks/useSocialSentiment'

import { FoldCard } from './FoldCard'

interface SentimentFeedCardProps {
  className?: string
  stretch?: boolean
}

/** 工作台情绪流条数：卡片内滚动展示最近判断。 */
const MAX_ITEMS = 8

/** 大V情绪流卡片：与资讯中心「大V情绪」同源（判断任务 10 分钟一轮，60s 轮询跟上节拍）。 */
export function SentimentFeedCard({ className, stretch }: SentimentFeedCardProps) {
  const { data, isLoading } = useSentimentFeed(1, MAX_ITEMS, { hours: 24 })
  const items = data?.items ?? []

  return (
    <FoldCard
      title="大V情绪"
      extra={
        <Link to="/news" className="text-xs">
          更多情绪
        </Link>
      }
      className={className}
      stretch={stretch}
    >
      {isLoading ? (
        <div className="flex justify-center py-6">
          <Spin />
        </div>
      ) : items.length ? (
        <div className="flex flex-1 min-h-0 flex-col overflow-y-auto">
          {items.map((item) => (
            <SentimentCard key={item.postId} item={item} />
          ))}
        </div>
      ) : (
        <Empty
          description="暂无大V情绪数据"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      )}
      <div className="pt-2 text-[10px] text-gray-600 border-t border-dashed border-gray-800">
        抖音大V视频 AI 判断 · 近 24 小时 · {SENTIMENT_REFETCH_INTERVAL / 1000}s 自动刷新
      </div>
    </FoldCard>
  )
}
