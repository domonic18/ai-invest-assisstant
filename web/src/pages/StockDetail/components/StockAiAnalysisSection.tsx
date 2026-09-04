import { LoadingOutlined, ReloadOutlined, RobotOutlined } from '@ant-design/icons'
import { Button, Card, DatePicker, Empty, Typography, message } from 'antd'
import dayjs, { type Dayjs } from 'dayjs'
import { useEffect, useRef, useState } from 'react'

import { MarkdownText } from '@/components/common/MarkdownText'
import { useGenerateStockAiAnalysis, useStockAiAnalysis } from '@/hooks/useStocks'
import { apiErrorMessage } from '@/utils/errorMessage'

interface StockAiAnalysisSectionProps {
  stockCode: string
}

// 生成派发到异步任务后，worker 取锁有延迟，轮询初期可能短暂看到 none
const NONE_GRACE_MS = 10_000

export function StockAiAnalysisSection({ stockCode }: StockAiAnalysisSectionProps) {
  const [tradeDate, setTradeDate] = useState<string | undefined>(undefined)
  const [pending, setPending] = useState(false)
  const pendingSinceRef = useRef(0)
  const { data: status, isLoading, isError, error, refetch } = useStockAiAnalysis(
    stockCode,
    tradeDate,
    (query) => (pending || query.state.data?.status === 'running' ? 3000 : false),
  )
  const generateMutation = useGenerateStockAiAnalysis(stockCode)
  const data = status?.data ?? null

  useEffect(() => {
    if (!pending || !status) return
    if (status.status === 'ready') {
      setPending(false)
      message.success('分析完成，已刷新结果')
    } else if (
      status.status === 'none' &&
      Date.now() - pendingSinceRef.current > NONE_GRACE_MS
    ) {
      setPending(false)
      message.error('生成失败或数据未就绪，请稍后重试')
    }
  }, [pending, status])

  const generate = (regenerate: boolean) => {
    generateMutation.mutate(
      { tradeDate, regenerate },
      {
        onSuccess: (result) => {
          if (result.status === 'ready') {
            message.success(result.data?.cached ? '已有当日分析，直接展示缓存' : '分析已生成')
            return
          }
          pendingSinceRef.current = Date.now()
          setPending(true)
          message.info('分析生成中，完成后自动刷新')
        },
        onError: (err) => message.error(apiErrorMessage(err, '生成失败，请稍后重试')),
      },
    )
  }

  const datePicker = (
    <DatePicker
      size="small"
      value={tradeDate ? dayjs(tradeDate) : undefined}
      placeholder="最近交易日"
      allowClear
      disabledDate={(d: Dayjs) => d.isAfter(dayjs(), 'day')}
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
          <Button
            size="small"
            type="primary"
            ghost
            icon={<ReloadOutlined />}
            loading={generateMutation.isPending}
            onClick={() => generate(true)}
          >
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
            <Button
              size="small"
              type="primary"
              loading={generateMutation.isPending}
              onClick={() => generate(false)}
            >
              生成{tradeDate ? `${tradeDate} ` : '当日 '}分析
            </Button>
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
        模型: {data.model ?? '-'} · 生成时间:{' '}
        {new Date(data.generatedAt).toLocaleString('zh-CN')}
        {data.cached && ' · 缓存'}
      </div>
      <div className="text-center text-xs text-gray-500">
        内容由 AI 生成，仅供参考，不构成投资建议
      </div>
    </div>
  )
}
