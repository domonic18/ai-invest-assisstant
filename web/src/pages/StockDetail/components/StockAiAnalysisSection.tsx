import { CalendarOutlined, LoadingOutlined, ReloadOutlined } from '@ant-design/icons'
import { Button, DatePicker, Empty, message } from 'antd'
import dayjs, { type Dayjs } from 'dayjs'
import { useEffect, useMemo, useState } from 'react'

import { MarkdownText } from '@/components/common/MarkdownText'
import { usePageAssistantResult } from '@/hooks/usePageAssistantResult'
import { useStockAiAnalysis, useStockAiAnalysisDates } from '@/hooks/useStocks'
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
  const { data: analysisDates, refetch: refetchDates } =
    useStockAiAnalysisDates(stockCode)
  const recordedDates = useMemo(
    () => new Set(analysisDates ?? []),
    [analysisDates],
  )
  const data = status?.data ?? null
  // 后端把显式非交易日归位到不晚于该日的最近交易日；生成与展示一律以
  // 归位后的有效交易日为准，避免对周末/节假日发起无意义分析
  const effectiveDate = status?.tradeDate

  usePageAssistantResult('stock_daily_analysis.complete', (event) => {
    if (event.stockCode !== stockCode) return false
    setAnalyzing(false)
    void refetch()
    void refetchDates()
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
      variant="borderless"
      format="MM-DD"
      value={pickerDate ? dayjs(pickerDate) : undefined}
      placeholder="交易日"
      allowClear
      suffixIcon={<CalendarOutlined className="!text-[10px] !text-[#5c616e]" />}
      disabledDate={(d: Dayjs) =>
        d.isAfter(dayjs(), 'day') || d.day() === 0 || d.day() === 6
      }
      cellRender={(current, info) => {
        if (info.type !== 'date' || !dayjs.isDayjs(current)) return info.originNode
        const iso = current.format('YYYY-MM-DD')
        const hasRecord = recordedDates.has(iso)
        return (
          <div
            className="ant-picker-cell-inner relative"
            title={hasRecord ? `${iso} 已生成分析` : undefined}
          >
            {current.date()}
            {hasRecord && (
              <span className="absolute bottom-[2px] left-1/2 -translate-x-1/2 w-[4px] h-[4px] rounded-full bg-[#5e6ad2]" />
            )}
          </div>
        )
      }}
      onChange={(d: Dayjs | null) => setTradeDate(d ? d.format('YYYY-MM-DD') : undefined)}
    />
  )

  const header = (
    <div className="flex items-center flex-nowrap gap-2 px-3.5 py-2.5 border-b border-[#23262d]">
      <span className="text-[13px] font-semibold whitespace-nowrap text-[#f0f1f5]">
        AI 分析解读
      </span>
      <div className="ml-auto flex items-center flex-nowrap gap-1">
        {datePicker}
        {data && (
          <button
            type="button"
            onClick={startAnalysis}
            className="shrink-0 whitespace-nowrap inline-flex items-center gap-1 px-2 py-[5px] text-xs rounded-md text-[#8a8f98] bg-transparent border border-transparent transition-colors hover:bg-[#1c1f26] hover:text-[#f0f1f5]"
          >
            <ReloadOutlined style={{ fontSize: 12 }} />
            重新生成
          </button>
        )}
      </div>
    </div>
  )

  if (isLoading) {
    return (
      <div>
        {header}
        <div className="p-3.5 text-sm text-[#8a8f98]">加载 AI 分析内容…</div>
      </div>
    )
  }

  if (isError) {
    return (
      <div>
        {header}
        <Empty
          className="py-4"
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
      <div>
        {header}
        <div className="p-3.5 flex items-center gap-2 text-sm text-[#8a8f98]">
          <LoadingOutlined spin />
          AI 分析生成中，完成后自动展示…
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <div>
        {header}
        <Empty
          className="py-4"
          description="该交易日尚未生成 AI 分析"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        >
          <div className="space-y-2">
            <Button size="small" type="primary" onClick={startAnalysis}>
              生成{effectiveDate ? ` ${effectiveDate} ` : '当日 '}分析
            </Button>
            <div className="text-xs text-[#5c616e]">
              点击后将在 AI 助手侧边栏执行分析，完成后自动展示
              {analyzing && '；分析进行中，进展见右侧 AI 助手'}
            </div>
            <div className="text-xs text-[#5c616e]">
              开启自选股分组的 AI 复盘后，每个交易日收盘自动生成
            </div>
          </div>
        </Empty>
      </div>
    )
  }

  const sections = data.sections.filter((section) => section.content)

  return (
    <div>
      {header}
      {analyzing && (
        <div className="px-3.5 pt-2 flex items-center gap-2 text-xs text-[#8a8f98]">
          <LoadingOutlined spin />
          分析进行中，进展见右侧 AI 助手…
        </div>
      )}
      <div className="px-3.5 pb-3">
        {sections.length ? (
          sections.map((section, i) => (
            <div
              key={section.key}
              className={`flex gap-2.5 py-2.5 ${
                i < sections.length - 1 ? 'border-b border-[#23262d]' : ''
              }`}
            >
              <span className="shrink-0 w-[60px] pt-0.5 text-xs font-semibold text-[#5e6ad2]">
                {section.title}
              </span>
              <div className="flex-1 min-w-0 text-xs text-[#8a8f98] leading-[1.75]">
                <MarkdownText content={section.content} />
              </div>
            </div>
          ))
        ) : (
          <Empty
            className="py-4"
            description="当日分析内容为空"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        )}
        <div className="mt-2.5 pt-2.5 border-t border-dashed border-[#23262d] font-mono text-[11px] text-[#5c616e]">
          模型 {data.model ?? '-'} · {data.tradeDate} · 生成{' '}
          {new Date(data.generatedAt).toLocaleString('zh-CN')}
          {data.cached && ' · 命中缓存'}
        </div>
        <div className="mt-2 text-[10px] text-[#5c616e]">
          以上内容由 AI 生成，不构成投资建议，请结合自身风险承受能力独立决策。
        </div>
      </div>
    </div>
  )
}
