import { LoadingOutlined, ReloadOutlined, RobotOutlined } from '@ant-design/icons'
import { Button, Card, DatePicker, Empty, Typography, message } from 'antd'
import dayjs, { type Dayjs } from 'dayjs'
import { useEffect, useState } from 'react'

import { MarkdownText } from '@/components/common/MarkdownText'
import { usePageAssistantResult } from '@/hooks/usePageAssistantResult'
import { useStockAiAnalysis } from '@/hooks/useStocks'
import { useAssistantStore } from '@/stores/assistant'

interface StockAiAnalysisSectionProps {
  stockCode: string
}

export function StockAiAnalysisSection({ stockCode }: StockAiAnalysisSectionProps) {
  const [tradeDate, setTradeDate] = useState<string | undefined>(undefined)
  const [analyzing, setAnalyzing] = useState(false)
  const panelOpen = useAssistantStore((state) => state.open)
  const { data: status, isLoading, isError, error, refetch } = useStockAiAnalysis(
    stockCode,
    tradeDate,
  )
  const data = status?.data ?? null
  // 后端把显式非交易日归位到不晚于该日的最近交易日；生成与展示一律以
  // 归位后的有效交易日为准，避免对周末/节假日发起无意义分析
  const effectiveDate = status?.tradeDate

  usePageAssistantResult('stock_daily_analysis.complete', (event) => {
    if (event.stockCode !== stockCode) return false
    setAnalyzing(false)
    void refetch()
    message.success('AI 分析完成，已刷新结果')
    return true
  })

  // 侧边栏关闭（含 agent 中途失败被放弃）时解除本区的进行中提示
  useEffect(() => {
    if (!panelOpen) setAnalyzing(false)
  }, [panelOpen])

  // 生成入口走 AI 助手侧边栏：agent 按 SKILL.md 取数分析，过程全程可见，
  // 完成后经 pageResult 事件回写刷新本区
  const startAnalysis = () => {
    setAnalyzing(true)
    useAssistantStore
      .getState()
      .sendQuestion(
        `请生成 ${stockCode}（${effectiveDate ?? '最近交易日'}） 的每日个股分析`
      )
  }

  const pickerDate = tradeDate ?? effectiveDate
  const datePicker = (
    <DatePicker
      size="small"
      value={pickerDate ? dayjs(pickerDate) : undefined}
      placeholder="最近交易日"
      allowClear
      disabledDate={(d: Dayjs) =>
        d.isAfter(dayjs(), 'day') || d.day() === 0 || d.day() === 6
      }
      onChange={(d: Dayjs | null) => setTradeDate(d ? d.format('YYYY-MM-DD') : undefined)}
    />
  )

  const header = (
    <div className="flex items-center justify-between mb-3">
      <Typography.Text className="text-gray-400 text-xs tracking-widest">
        AI 分析解读
      </Typography.Text>
      <div className="flex items-center gap-2">
        {datePicker}
        {data && (
          <Button size="small" type="primary" ghost icon={<ReloadOutlined />} onClick={startAnalysis}>
            重新生成
          </Button>
        )}
      </div>
    </div>
  )

  if (isLoading) {
    return (
      <div className="p-3">
        {header}
        <div className="text-sm text-gray-400">加载 AI 分析内容…</div>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="p-3">
        {header}
        <Empty
          description={error instanceof Error ? error.message : '加载失败'}
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        >
          <Button size="small" onClick={() => refetch()}>
            重试
          </Button>
        </Empty>
      </div>
    )
  }

  if (status?.status === 'running') {
    return (
      <div className="p-3">
        {header}
        <div className="flex items-center gap-2 text-sm text-gray-400">
          <LoadingOutlined spin />
          AI 分析生成中，完成后自动展示…
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="p-3">
        {header}
        <Empty
          description="该交易日尚未生成 AI 分析"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        >
          <div className="space-y-2">
            <Button size="small" type="primary" onClick={startAnalysis}>
              生成{effectiveDate ? ` ${effectiveDate} ` : '当日 '}分析
            </Button>
            <div className="text-xs text-gray-500">
              点击后将在 AI 助手侧边栏执行分析，完成后自动展示
              {analyzing && '；分析进行中，进展见右侧 AI 助手'}
            </div>
            <div className="text-xs text-gray-500">
              开启自选股分组的 AI 复盘后，每个交易日收盘自动生成
            </div>
          </div>
        </Empty>
      </div>
    )
  }

  const sections = data.sections.filter((section) => section.content)

  return (
    <div className="p-3 space-y-3">
      {header}
      {analyzing && (
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <LoadingOutlined spin />
          分析进行中，进展见右侧 AI 助手…
        </div>
      )}
      {sections.length ? (
        sections.map((section) => (
          <Card
            key={section.key}
            variant="borderless"
            size="small"
            title={
              <span>
                <RobotOutlined className="mr-2" />
                {section.title}
              </span>
            }
          >
            <div className="text-sm">
              <MarkdownText content={section.content} />
            </div>
          </Card>
        ))
      ) : (
        <Empty description="当日分析内容为空" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      )}
      <div className="text-xs text-gray-500">
        模型: {data.model ?? '-'} · 数据日期: {data.tradeDate} · 生成时间:{' '}
        {new Date(data.generatedAt).toLocaleString('zh-CN')}
        {data.cached && ' · 缓存'}
      </div>
      <div className="text-center text-xs text-gray-500">
        内容由 AI 生成，仅供参考，不构成投资建议
      </div>
    </div>
  )
}
