import { RobotOutlined } from '@ant-design/icons'
import { useQueryClient } from '@tanstack/react-query'
import { Button, Card, Empty, Input, message, Popconfirm, Tag, Typography } from 'antd'
import { useState } from 'react'

import {
  generateMarketReview,
  NonTradingDayError,
  saveMarketReviewSection,
} from '@/api/market'
import { MarkdownText } from '@/components/common/MarkdownText'
import { useMarketReview } from '@/hooks/useMarket'
import { useAuthStore } from '@/stores/auth'
import type { MarketReview, MarketReviewSection } from '@ai-invest/shared'

interface ReviewCardProps {
  section: MarketReviewSection
  edited: boolean
  editing: boolean
  saving: boolean
  onStartEdit: () => void
  onCancelEdit: () => void
  onSave: (content: string) => void
}

function ReviewCard({
  section,
  edited,
  editing,
  saving,
  onStartEdit,
  onCancelEdit,
  onSave,
}: ReviewCardProps) {
  const [draft, setDraft] = useState('')

  const handleStart = () => {
    setDraft(section.content)
    onStartEdit()
  }

  return (
    <Card
      variant="borderless"
      size="small"
      title={
        <span>
          <RobotOutlined className="mr-2" />
          {section.title}
        </span>
      }
      extra={
        <span className="inline-flex items-center gap-2">
          {edited ? <Tag color="orange">已编辑</Tag> : <Tag color="purple">AI 生成</Tag>}
          {editing ? (
            <>
              <Button size="small" onClick={onCancelEdit} disabled={saving}>
                取消
              </Button>
              <Button
                size="small"
                type="primary"
                loading={saving}
                onClick={() => onSave(draft)}
              >
                保存
              </Button>
            </>
          ) : (
            <Button size="small" type="text" onClick={handleStart}>
              编辑
            </Button>
          )}
        </span>
      }
    >
      {editing ? (
        <Input.TextArea
          value={draft}
          autoSize={{ minRows: 4 }}
          onChange={(e) => setDraft(e.target.value)}
        />
      ) : (
        <div className="text-sm">
          <MarkdownText content={section.content} />
        </div>
      )}
    </Card>
  )
}

interface AiReviewSectionProps {
  tradeDate?: string
}

export function AiReviewSection({ tradeDate }: AiReviewSectionProps) {
  const queryClient = useQueryClient()
  const isAdmin = useAuthStore((state) => state.isAdmin)
  const [generating, setGenerating] = useState(false)
  const [editingKey, setEditingKey] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
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

  const handleSaveSection = async (sectionKey: string, content: string) => {
    if (!data) return
    if (!content.trim()) {
      message.warning('内容不能为空')
      return
    }
    setSaving(true)
    try {
      const review = await saveMarketReviewSection(data.tradeDate, sectionKey, content)
      setReviewCache(review)
      setEditingKey(null)
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
          {isAdmin && (
            <Button
              type="primary"
              loading={generating}
              onClick={() => handleGenerate(false)}
            >
              {generating ? 'AI 生成中，通常需要 10-30 秒…' : '生成 AI 复盘'}
            </Button>
          )}
        </Empty>
      </Card>
    )
  }

  const regenerateButton = isAdmin ? (
    <Button
      size="small"
      loading={generating}
      onClick={() => handleGenerate(true)}
      disabled={editingKey !== null}
    >
      重新生成
    </Button>
  ) : null

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Typography.Text className="text-gray-400 text-xs tracking-widest">
          AI 复盘解读
        </Typography.Text>
        {isAdmin &&
          (data.edited ? (
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
          ))}
      </div>
      {data.sections.map((section) => (
        <ReviewCard
          key={section.key}
          section={section}
          edited={data.edited}
          editing={editingKey === section.key}
          saving={saving}
          onStartEdit={() => setEditingKey(section.key)}
          onCancelEdit={() => setEditingKey(null)}
          onSave={(content) => handleSaveSection(section.key, content)}
        />
      ))}
      <div className="text-xs text-gray-500">
        模型: {data.model ?? '-'} · 生成时间:{' '}
        {new Date(data.generatedAt).toLocaleString('zh-CN')}
        {data.cached && ' · 缓存'}
        {data.edited && ' · 人工编辑'}
      </div>
    </div>
  )
}
