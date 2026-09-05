import { RobotOutlined } from '@ant-design/icons'
import { useQueryClient } from '@tanstack/react-query'
import { Button, Card, Empty, Input, message, Popconfirm, Tag, Typography } from 'antd'
import { useEffect, useState } from 'react'

import { NonTradingDayError, saveMarketReviewSection } from '@/api/market'
import { MarkdownText } from '@/components/common/MarkdownText'
import { useMarketReview } from '@/hooks/useMarket'
import { usePageAssistantResult } from '@/hooks/usePageAssistantResult'
import { useAssistantStore } from '@/stores/assistant'
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
  const panelOpen = useAssistantStore((state) => state.open)
  const [generating, setGenerating] = useState(false)
  const [editingKey, setEditingKey] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const { data, isLoading, isError, error, refetch } = useMarketReview(tradeDate)

  const setReviewCache = (review: MarketReview) => {
    queryClient.setQueryData(['market', 'ai-review', tradeDate], review)
  }

  // 生成入口走 AI 助手侧边栏：agent 按 SKILL.md 工具取数分析，过程全程可见，
  // 完成后经 pageResult 事件回写刷新本区
  const handleGenerate = (regenerate: boolean) => {
    setGenerating(true)
    useAssistantStore
      .getState()
      .sendQuestion(
        `请${regenerate ? '重新' : ''}生成 ${tradeDate ?? '最近交易日'} 的大盘每日复盘`
      )
  }

  usePageAssistantResult('market_daily_review.complete', () => {
    setGenerating(false)
    void refetch()
    message.success('复盘已生成，已刷新')
    return true
  })

  // 侧边栏关闭（含 agent 中途失败被放弃）时解除本区的进行中提示
  useEffect(() => {
    if (!panelOpen) setGenerating(false)
  }, [panelOpen])

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
          <div className="space-y-2">
            <Button
              type="primary"
              loading={generating}
              onClick={() => handleGenerate(false)}
            >
              {generating ? 'AI 生成中，进展见右侧 AI 助手…' : '生成 AI 复盘'}
            </Button>
            <div className="text-xs text-gray-500">
              点击后将在 AI 助手侧边栏执行分析，完成后自动展示
            </div>
            <div className="text-xs text-gray-500">每个交易日收盘后由定时任务自动生成</div>
          </div>
        </Empty>
      </Card>
    )
  }

  const regenerateButton = (
    <Button
      size="small"
      loading={generating}
      onClick={() => handleGenerate(true)}
      disabled={editingKey !== null}
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
        {generating && (
          <span className="text-xs text-gray-400">AI 生成中，进展见右侧 AI 助手…</span>
        )}
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
