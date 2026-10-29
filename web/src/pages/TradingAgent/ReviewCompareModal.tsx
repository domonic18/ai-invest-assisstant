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
  ApiTradingAgentReviewMetrics,
  TradingAgentReviewCompareWindow,
  TradingAgentReviewWindow,
  TradingReviewPeriod,
  TradingReviewScope,
} from '@ai-invest/shared'

import { useCompareTradingAgentReviews } from '@/hooks/useTradingAgent'
import { useColorScheme } from '@/stores/settings'
import { changeHex, DATE_FORMAT, formatNumber, formatPercent } from '@/utils/formatters'

import { describeWindow, REVIEW_PERIOD_OPTIONS } from './reviewMeta'

const SCOPE_OPTIONS = [
  { label: '本期', value: 'current' },
  { label: '上期', value: 'previous' },
]

interface CompareRow {
  key: string
  label: string
  /** 数值指标（同一口径）；null = 至少一侧不可计算。 */
  pick: (metrics: ApiTradingAgentReviewMetrics) => number | null
  format: (value: number) => string
  colored?: boolean
}

const ROWS: CompareRow[] = [
  {
    key: 'returnPct',
    label: '区间收益',
    pick: (m) => m.returnPct,
    format: (v) => formatPercent(v),
    colored: true,
  },
  {
    key: 'annualized',
    label: '年化收益',
    pick: (m) => m.annualizedReturnPct,
    format: (v) => formatPercent(v),
    colored: true,
  },
  {
    key: 'drawdown',
    label: '最大回撤',
    pick: (m) => m.maxDrawdownPct,
    format: (v) => `-${formatNumber(v)}%`,
  },
  {
    key: 'excess',
    label: '超额收益',
    pick: (m) => m.excessReturnPct,
    format: (v) => formatPercent(v),
    colored: true,
  },
  {
    key: 'winRate',
    label: '胜率',
    pick: (m) => m.winRatePct,
    format: (v) => formatPercent(v),
  },
  {
    key: 'plRatio',
    label: '盈亏比',
    pick: (m) => m.profitLossRatio,
    format: (v) => formatNumber(v),
  },
  {
    key: 'turnover',
    label: '换手率',
    pick: (m) => m.turnoverRatePct,
    format: (v) => formatPercent(v),
  },
  {
    key: 'deviation',
    label: '执行偏差',
    pick: (m) => m.executionDeviationPct,
    format: (v) => formatPercent(v),
  },
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
  const [result, setResult] = useState<ApiTradingAgentReviewCompareResponse | null>(null)
  const compare = useCompareTradingAgentReviews(agentKey)

  useEffect(() => {
    if (!open) return
    setPeriod(baseWindow.period ?? 'month')
    setScope('previous')
    setTradeDate(null)
    setResult(null)
  }, [open, baseWindow.period])

  const windowB = useMemo(() => draftToWindow(period, scope, tradeDate), [period, scope, tradeDate])

  const runCompare = () => {
    compare.mutate(
      { windowA: baseWindow, windowB },
      { onSuccess: (data) => setResult(data) },
    )
  }

  const compareColumns = [
    { title: '指标', dataIndex: 'label', width: 100 },
    { title: `A · ${describeWindow(baseWindow)}`, dataIndex: 'a', width: 150 },
    { title: `B · ${describeWindow(windowB)}`, dataIndex: 'b', width: 150 },
  ]

  const compareRows = result
    ? ROWS.map((row) => ({
        key: row.key,
        label: row.label,
        a: renderCompareValue(row.pick(result.windowA), row),
        b: renderCompareValue(row.pick(result.windowB), row),
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

        {result ? (
          <>
            <Alert
              type="info"
              showIcon
              message={`按 ${result.alignedTradingDays} 个交易日对齐`}
              description={result.note}
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
function renderCompareValue(value: number | null, row: CompareRow): ReactNode {
  if (value === null) return '-'
  return (
    <span style={row.colored ? { color: changeHex(value) } : undefined}>{row.format(value)}</span>
  )
}
