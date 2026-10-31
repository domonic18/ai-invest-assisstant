/**
 * 跨窗口复盘指标对比（§4.5）：当前窗口 A 与可选窗口 B 按等长交易日对齐后同屏。
 *
 * A 固定为面板当前窗口（可能是本期/上期/自定义区间）；B 可选周期、作用域与
 * 基准日，默认同周期上期。两个窗口都须已生成，否则后端 404 提示先生成。
 */

import { Alert, DatePicker, Modal, Select, Space, Table } from 'antd'
import dayjs, { type Dayjs } from 'dayjs'
import { useEffect, useMemo, useState, type ReactNode } from 'react'

import type {
  ApiTradingAgentReviewCompareResponse,
  TradingAgentReviewCompareWindow,
  TradingAgentReviewWindow,
  TradingReviewPeriod,
  TradingReviewScope,
} from '@ai-invest/shared'

import { useCompareTradingAgentReviews } from '@/hooks/useTradingAgent'
import { useColorScheme } from '@/stores/settings'
import { DATE_FORMAT } from '@/utils/formatters'

import { describeWindow, REVIEW_PERIOD_OPTIONS } from './reviewMeta'
import {
  compareMetricColor,
  COMPARE_METRIC_ROWS,
  type ReviewMetricRow,
} from './reviewMetricsMeta'

const SCOPE_OPTIONS = [
  { label: '本期', value: 'current' },
  { label: '上期', value: 'previous' },
]

function draftToWindow(
  period: TradingReviewPeriod,
  scope: TradingReviewScope,
  tradeDate: Dayjs | null,
): TradingAgentReviewCompareWindow {
  return {
    period,
    scope,
    tradeDate: tradeDate?.format(DATE_FORMAT),
  }
}

/** 一次对比结果的快照：表头与数据必须同源，避免草稿改动后表头与数值错位。 */
interface CompareSnapshot {
  data: ApiTradingAgentReviewCompareResponse
  windowA: TradingAgentReviewWindow
  windowB: TradingAgentReviewCompareWindow
}

interface ReviewCompareModalProps {
  open: boolean
  onClose: () => void
  agentKey: string
  /** 面板当前窗口（对比 A）。 */
  baseWindow: TradingAgentReviewWindow
}

export function ReviewCompareModal({
  open,
  onClose,
  agentKey,
  baseWindow,
}: ReviewCompareModalProps) {
  useColorScheme()
  const defaultPeriod = baseWindow.period ?? 'month'
  const [period, setPeriod] = useState<TradingReviewPeriod>(defaultPeriod)
  const [scope, setScope] = useState<TradingReviewScope>('previous')
  const [tradeDate, setTradeDate] = useState<Dayjs | null>(null)
  const [snapshot, setSnapshot] = useState<CompareSnapshot | null>(null)
  const compare = useCompareTradingAgentReviews(agentKey)

  useEffect(() => {
    if (!open) return
    setPeriod(baseWindow.period ?? 'month')
    setScope('previous')
    setTradeDate(null)
    setSnapshot(null)
  }, [open, baseWindow.period])

  const windowB = useMemo(() => draftToWindow(period, scope, tradeDate), [period, scope, tradeDate])

  const runCompare = () => {
    // 请求窗口与结果一起快照：草稿后续改动不影响已渲染的表头
    const requestA = baseWindow
    const requestB = windowB
    compare.mutate(
      { windowA: requestA, windowB: requestB },
      {
        onSuccess: (data) =>
          setSnapshot({ data, windowA: requestA, windowB: requestB }),
      },
    )
  }

  const compareColumns = snapshot
    ? [
        { title: '指标', dataIndex: 'label', width: 100 },
        { title: `A · ${describeWindow(snapshot.windowA)}`, dataIndex: 'a', width: 150 },
        { title: `B · ${describeWindow(snapshot.windowB)}`, dataIndex: 'b', width: 150 },
      ]
    : []

  const compareRows = snapshot
    ? COMPARE_METRIC_ROWS.map((row) => ({
        key: row.key,
        label: row.label,
        a: renderCompareValue(row.pick(snapshot.data.windowA), row),
        b: renderCompareValue(row.pick(snapshot.data.windowB), row),
      }))
    : []

  return (
    <Modal
      open={open}
      onCancel={onClose}
      onOk={runCompare}
      okText="对比"
      confirmLoading={compare.isPending}
      width={680}
      title="复盘窗口对比"
      destroyOnClose
    >
      <Space direction="vertical" size="small" className="w-full">
        <div className="text-xs text-white/60">
          窗口 A：{describeWindow(baseWindow)}
          {baseWindow.period ? '（面板当前窗口）' : ''}
        </div>
        <Space size="small" wrap>
          <span className="text-xs text-white/60">窗口 B</span>
          <Select<TradingReviewPeriod>
            size="small"
            value={period}
            onChange={setPeriod}
            options={REVIEW_PERIOD_OPTIONS}
            style={{ width: 80 }}
          />
          <Select<TradingReviewScope>
            size="small"
            value={scope}
            onChange={setScope}
            options={SCOPE_OPTIONS}
            style={{ width: 90 }}
          />
          <DatePicker
            size="small"
            value={tradeDate}
            onChange={setTradeDate}
            allowClear
            placeholder="最新一期"
            disabledDate={(current: Dayjs) => current.isAfter(dayjs(), 'day')}
          />
        </Space>

        {snapshot ? (
          <>
            <Alert
              type="info"
              showIcon
              message={`按 ${snapshot.data.alignedTradingDays} 个交易日对齐`}
              description={snapshot.data.note}
            />
            <Table<{ key: string; label: string; a: ReactNode; b: ReactNode }>
              size="small"
              pagination={false}
              columns={compareColumns}
              dataSource={compareRows}
              rowKey="key"
            />
          </>
        ) : (
          <EmptyHint />
        )}
      </Space>
    </Modal>
  )
}

/** 未对比前的结果区占位（避免 Modal 空白跳动）。 */
function EmptyHint() {
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-6 text-center text-xs text-white/40">
      选择窗口 B 后点击「对比」；两个窗口都须已生成复盘。
    </div>
  )
}

/** 表内数值：null → '-'；收益类指标按正负着色，其余中性。 */
function renderCompareValue(value: number | null, row: ReviewMetricRow): ReactNode {
  if (value === null) return '-'
  const color = compareMetricColor(value, row.tone)
  return <span style={color ? { color } : undefined}>{row.format(value)}</span>
}
