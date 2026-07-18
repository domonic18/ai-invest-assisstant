import { RobotOutlined } from '@ant-design/icons'
import { useQueryClient } from '@tanstack/react-query'
import { Button, Card, Empty, message, Tag, Typography } from 'antd'
import { useState } from 'react'

import { fetchMarketReview } from '@/api/market'
import { useMarketReview } from '@/hooks/useMarket'
import type { MarketReview } from '@ai-invest/shared'

interface ReviewCardProps {
  title: string
  content: string
}

function ReviewCard({ title, content }: ReviewCardProps) {
  return (
    <Card
      variant="borderless"
      size="small"
      title={
        <span>
          <RobotOutlined className="mr-2" />
          {title}
        </span>
      }
      extra={<Tag color="purple">AI 生成</Tag>}
    >
      <Typography.Paragraph className="!mb-0 text-sm whitespace-pre-wrap">
        {content}
      </Typography.Paragraph>
    </Card>
  )
}

interface AiReviewSectionProps {
  tradeDate?: string
}

export function AiReviewSection({ tradeDate }: AiReviewSectionProps) {
  const queryClient = useQueryClient()
  const [requested, setRequested] = useState(false)
  const [regenerating, setRegenerating] = useState(false)
  const { data, isLoading, isError, error } = useMarketReview(requested, tradeDate)

  const handleGenerate = async () => {
    setRequested(true)
  }

  const handleRegenerate = async () => {
    setRegenerating(true)
    try {
      const review = await fetchMarketReview(true, tradeDate)
      queryClient.setQueryData(['market', 'ai-review', tradeDate], review)
      message.success('已重新生成')
    } catch (err) {
      message.error(err instanceof Error ? err.message : '生成失败')
    } finally {
      setRegenerating(false)
    }
  }

  if (!requested) {
    return (
      <Card
        variant="borderless"
        title={
          <span>
            <RobotOutlined className="mr-2" />
            AI 大盘综述
          </span>
        }
      >
        <Empty
          description="基于当日行情、涨停与板块资金数据生成复盘综述"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        >
          <Button type="primary" onClick={handleGenerate}>
            生成 AI 复盘
          </Button>
        </Empty>
      </Card>
    )
  }

  if (isLoading) {
    return (
      <Card variant="borderless" title="AI 大盘综述">
        <div className="text-sm text-gray-400">AI 正在生成复盘综述，通常需要 10-30 秒…</div>
      </Card>
    )
  }

  if (isError || !data) {
    return (
      <Card variant="borderless" title="AI 大盘综述">
        <Empty
          description={error instanceof Error ? error.message : '生成失败，请检查 LLM 配置'}
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        >
          <Button onClick={handleRegenerate} loading={regenerating}>
            重试
          </Button>
        </Empty>
      </Card>
    )
  }

  const review: MarketReview = data

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Typography.Text className="text-gray-400 text-xs tracking-widest">
          AI 复盘解读
        </Typography.Text>
        <Button size="small" onClick={handleRegenerate} loading={regenerating}>
          重新生成
        </Button>
      </div>
      <ReviewCard title="AI 大盘综述" content={review.overview} />
      <ReviewCard title="情绪与连板分析" content={review.emotionAnalysis} />
      <ReviewCard title="资金面分析" content={review.capitalAnalysis} />
      <ReviewCard title="风险提示与策略建议" content={review.riskAdvice} />
      <div className="text-xs text-gray-500">
        模型: {review.model ?? '-'} · 生成时间: {new Date(review.generatedAt).toLocaleString('zh-CN')}
        {review.cached && ' · 缓存'}
      </div>
    </div>
  )
}
