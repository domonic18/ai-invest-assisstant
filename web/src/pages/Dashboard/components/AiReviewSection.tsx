import { RobotOutlined } from '@ant-design/icons'
import { useQueryClient } from '@tanstack/react-query'
import { Button, Card, Empty, Input, message, Popconfirm, Tag, Typography } from 'antd'
import { useState } from 'react'

import { generateMarketReview, NonTradingDayError, saveMarketReview } from '@/api/market'
import { MarkdownText } from '@/components/common/MarkdownText'
import { useMarketReview } from '@/hooks/useMarket'
import type { MarketReview } from '@ai-invest/shared'

const SECTION_TITLES = {
  overview: 'AI 大盘综述',
  emotionAnalysis: '情绪与连板分析',
  capitalAnalysis: '资金面分析',
  riskAdvice: '风险提示与策略建议',
} as const

type SectionKey = keyof typeof SECTION_TITLES

const SECTION_KEYS = Object.keys(SECTION_TITLES) as SectionKey[]

type ReviewDraft = Record<SectionKey, string>

function toDraft(review: MarketReview): ReviewDraft {
  return {
    overview: review.overview,
    emotionAnalysis: review.emotionAnalysis,
    capitalAnalysis: review.capitalAnalysis,
    riskAdvice: review.riskAdvice,
  }
}

interface ReviewCardProps {
  title: string
  content: string
  edited: boolean
}

function ReviewCard({ title, content, edited }: ReviewCardProps) {
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
      extra={
        edited ? <Tag color="orange">已编辑</Tag> : <Tag color="purple">AI 生成</Tag>
      }
    >
      <div className="text-sm">
        <MarkdownText content={content} />
      </div>
    </Card>
  )
}

interface AiReviewSectionProps {
  tradeDate?: string
}

export function AiReviewSection({ tradeDate }: AiReviewSectionProps) {
  const queryClient = useQueryClient()
  const [generating, setGenerating] = useState(false)
  const [saving, setSaving] = useState(false)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<ReviewDraft | null>(null)
  const { data, isLoading, isError, error, refetch } = useMarketReview(tradeDate)

  const setReviewCache = (review: MarketReview) => {
    queryClient.setQueryData(['market', 'ai-review', tradeDate], review)
  }

  const handleGenerate = async (regenerate: boolean) => {
    setGenerating(true)
    try {
      const review = await generateMarketReview(regenerate, tradeDate)
      setReviewCache(review)
      message.success(regenerate ? '已重新生成' : '已生成 AI 复盘')
    } catch (err) {
      message.error(err instanceof Error ? err.message : '生成失败')
    } finally {
      setGenerating(false)
    }
  }

  const handleStartEdit = () => {
    if (!data) return
    setDraft(toDraft(data))
    setEditing(true)
  }

  const handleCancelEdit = () => {
    setDraft(null)
    setEditing(false)
  }

  const handleSave = async () => {
    if (!data || !draft) return
    setSaving(true)
    try {
      const review = await saveMarketReview({
        trade_date: data.tradeDate,
        overview: draft.overview,
        emotion_analysis: draft.emotionAnalysis,
        capital_analysis: draft.capitalAnalysis,
        risk_advice: draft.riskAdvice,
      })
      setReviewCache(review)
      setEditing(false)
      setDraft(null)
      message.success('复盘内容已保存')
    } catch (err) {
      message.error(err instanceof Error ? err.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  if (isLoading) {
    return (
      <Card variant="borderless" title="AI 大盘综述">
        <div className="text-sm text-gray-400">加载复盘内容…</div>
      </Card>
    )
  }

  if (isError) {
    if (error instanceof NonTradingDayError) {
      return (
        <Card variant="borderless" title="AI 大盘综述">
          <Empty
            description="该日不是交易日，无复盘内容"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        </Card>
      )
    }
    return (
      <Card variant="borderless" title="AI 大盘综述">
        <Empty
          description={error instanceof Error ? error.message : '加载失败'}
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        >
          <Button onClick={() => refetch()}>重试</Button>
        </Empty>
      </Card>
    )
  }

  if (!data) {
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
          <Button
            type="primary"
            loading={generating}
            onClick={() => handleGenerate(false)}
          >
            {generating ? 'AI 生成中，通常需要 10-30 秒…' : '生成 AI 复盘'}
          </Button>
        </Empty>
      </Card>
    )
  }

  const regenerateButton = (
    <Button
      size="small"
      loading={generating}
      onClick={() => handleGenerate(true)}
      disabled={editing}
    >
      重新生成
    </Button>
  )

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Typography.Text className="text-gray-400 text-xs tracking-widest">
          AI 复盘解读
        </Typography.Text>
        <div className="flex items-center gap-2">
          {editing ? (
            <>
              <Button size="small" onClick={handleCancelEdit} disabled={saving}>
                取消
              </Button>
              <Button
                size="small"
                type="primary"
                loading={saving}
                onClick={handleSave}
              >
                保存
              </Button>
            </>
          ) : (
            <>
              <Button size="small" onClick={handleStartEdit} disabled={generating}>
                编辑
              </Button>
              {data.edited ? (
                <Popconfirm
                  title="重新生成将覆盖人工编辑的内容"
                  okText="重新生成"
                  cancelText="取消"
                  onConfirm={() => handleGenerate(true)}
                >
                  {regenerateButton}
                </Popconfirm>
              ) : (
                regenerateButton
              )}
            </>
          )}
        </div>
      </div>
      {SECTION_KEYS.map((key) =>
        editing && draft ? (
          <Card
            key={key}
            variant="borderless"
            size="small"
            title={
              <span>
                <RobotOutlined className="mr-2" />
                {SECTION_TITLES[key]}
              </span>
            }
          >
            <Input.TextArea
              value={draft[key]}
              autoSize={{ minRows: 4 }}
              onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}
            />
          </Card>
        ) : (
          <ReviewCard
            key={key}
            title={SECTION_TITLES[key]}
            content={data[key]}
            edited={data.edited}
          />
        )
      )}
      <div className="text-xs text-gray-500">
        模型: {data.model ?? '-'} · 生成时间:{' '}
        {new Date(data.generatedAt).toLocaleString('zh-CN')}
        {data.cached && ' · 缓存'}
        {data.edited && ' · 人工编辑'}
      </div>
    </div>
  )
}
