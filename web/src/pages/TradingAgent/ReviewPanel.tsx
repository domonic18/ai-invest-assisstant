/**
 * AI 复盘卡片（RQ-001 六档周期）：日/周/月定时生成，季/半年/年按需生成。
 *
 * 三种窗口形态与后端读取/生成同口径：本期（周期至今）、上期（上一完整周期）、
 * 自定义区间（缺 period，由后端按跨度映射报告框架）。404 = 尚未生成，
 * noTargetReason 非空 = 已执行但空仓无复盘对象（与「未生成」区分）。
 * 生成走异步派发（logId 轮询采集日志），完成即失效复盘/日期缓存；
 * 对比入口把当前窗口作为 A，可选 B 打开跨窗口对齐对比。
 */
import { BarChartOutlined, ReloadOutlined } from '@ant-design/icons'
import {
  Alert,
  Button,
  Card,
  DatePicker,
  Descriptions,
  Empty,
  Segmented,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import dayjs, { type Dayjs } from 'dayjs'
import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'

import type {
  ApiTradingAgentMethodologyCheck,
  ApiTradingAgentReviewExperience,
  ApiTradingAgentTradeVerdict,
  TradingAgentReviewGenerateRequest,
  TradingAgentReviewWindow,
  TradingReviewPeriod,
  TradingReviewScope,
} from '@ai-invest/shared'

import { MarkedDatePicker } from '@/components/common/MarkedDatePicker'
import { queryKeys } from '@/hooks/queryKeys'
import {
  useGenerateTradingAgentReview,
  useReviewGenerationStatus,
  useTradingAgentDates,
  useTradingAgentReview,
} from '@/hooks/useTradingAgent'
import { DATE_FORMAT } from '@/utils/formatters'
import { useAgentKey } from './agentKeyContext'
import { ReviewCompareModal } from './ReviewCompareModal'
import { ReviewMetricsGrid } from './ReviewMetricsGrid'
import {
  AUTO_REVIEW_PERIODS,
  CUSTOM_RANGE_TOO_LONG,
  isRangeTooLong,
  REVIEW_PERIOD_LABELS,
  REVIEW_PERIOD_OPTIONS,
} from './reviewMeta'

const VERDICT_ITEMS: Record<string, { label: string; color: string }> = {
  correct: { label: '对', color: 'success' },
  wrong: { label: '错', color: 'error' },
  neutral: { label: '中性', color: 'default' },
}

const MEM_TYPE_LABELS: Record<ApiTradingAgentReviewExperience['memType'], string> = {
  discipline: '纪律',
  method: '方法',
  lesson: '教训',
}

const CHECK_VERDICT_ITEMS: Record<ApiTradingAgentMethodologyCheck['verdict'], { label: string; color: string }> = {
  followed: { label: '遵守', color: 'success' },
  violated: { label: '违反', color: 'error' },
  not_applicable: { label: '不适用', color: 'default' },
}

const SCOPE_OPTIONS = [
  { label: '本期', value: 'current' },
  { label: '上期', value: 'previous' },
]

function VerdictTag({ value }: { value: string }) {
  const item = VERDICT_ITEMS[value] ?? VERDICT_ITEMS.neutral
  return <Tag color={item.color}>{item.label}</Tag>
}

const verdictColumns = [
  { title: '代码', dataIndex: 'stockCode', width: 80 },
  {
    title: '选股',
    dataIndex: 'selectionVerdict',
    width: 64,
    render: (v: string) => <VerdictTag value={v} />,
  },
  {
    title: '计划',
    dataIndex: 'planVerdict',
    width: 64,
    render: (v: string) => <VerdictTag value={v} />,
  },
  {
    title: '执行',
    dataIndex: 'executionVerdict',
    width: 64,
    render: (v: string) => <VerdictTag value={v} />,
  },
  { title: '归因', dataIndex: 'reason', ellipsis: true },
]

/** 未生成态文案：按窗口形态区分自动/按需生成。 */
function emptyDescription(
  period: TradingReviewPeriod,
  scope: TradingReviewScope,
  range: [Dayjs, Dayjs] | null,
  tradeDate?: string,
): string {
  if (range) return '该区间尚未生成复盘，点击「生成复盘」按区间生成'
  const label = REVIEW_PERIOD_LABELS[period]
  if (!AUTO_REVIEW_PERIODS.includes(period)) {
    return scope === 'previous'
      ? `${label}上期按需生成，点击「生成复盘」触发`
      : `${label}档按需生成，点击「生成复盘」触发`
  }
  if (scope === 'previous') {
    return `上一${label}复盘尚未生成（每交易日 19:00 盘后自动生成）`
  }
  const when = tradeDate && dayjs(tradeDate).isBefore(dayjs(), 'day') ? '该日' : '当前'
  return `${when}${label}复盘尚未生成（每交易日 19:00 盘后自动生成）`
}

export function ReviewPanel() {
  const agentKey = useAgentKey()
  const queryClient = useQueryClient()
  const [period, setPeriod] = useState<TradingReviewPeriod>('day')
  const [scope, setScope] = useState<TradingReviewScope>('current')
  const [selectedDate, setSelectedDate] = useState<Dayjs | null>(null)
  const [range, setRange] = useState<[Dayjs, Dayjs] | null>(null)
  const [pendingLogId, setPendingLogId] = useState<number | null>(null)
  const generationStartedAt = useRef<number | null>(null)
  const [compareOpen, setCompareOpen] = useState(false)

  const window = useMemo<TradingAgentReviewWindow>(() => {
    if (range) {
      return { startDate: range[0].format(DATE_FORMAT), endDate: range[1].format(DATE_FORMAT) }
    }
    return {
      period,
      scope,
      tradeDate: selectedDate?.format(DATE_FORMAT),
    }
  }, [range, period, scope, selectedDate])

  const { data: review, isLoading } = useTradingAgentReview(agentKey, window)
  const { data: dates } = useTradingAgentDates(agentKey)
  const generate = useGenerateTradingAgentReview(agentKey)
  const generationQuery = useReviewGenerationStatus(pendingLogId)
  const generating = generate.isPending || pendingLogId !== null

  // 生成任务终态：成功失效复盘/日期缓存，失败提示（跳过的良性原因单独说明）
  useEffect(() => {
    if (pendingLogId === null) return
    // 兜底（15 分钟）：任务丢失时不无限轮询保持「生成中」
    const startedAt = generationStartedAt.current
    if (startedAt !== null && Date.now() - startedAt > 15 * 60 * 1000) {
      generationStartedAt.current = null
      setPendingLogId(null)
      message.warning('复盘生成任务长时间未返回，请稍后刷新查看')
      return
    }
    const status = generationQuery.data?.collector_status
    if (!status || !['success', 'partial', 'failed', 'skipped'].includes(status)) return
    generationStartedAt.current = null
    setPendingLogId(null)
    if (status === 'success' || status === 'partial') {
      message.success('复盘已生成')
      void queryClient.invalidateQueries({ queryKey: queryKeys.tradingAgent.reviewAll(agentKey) })
      void queryClient.invalidateQueries({ queryKey: queryKeys.tradingAgent.dates(agentKey) })
    } else if (status === 'skipped') {
      message.info('生成任务被跳过（可能已有进行中的生成），请稍后刷新')
    } else {
      message.error('复盘生成失败，请稍后重试或查看采集日志')
    }
  }, [generationQuery, pendingLogId, agentKey, queryClient])

  const changePeriod = (next: TradingReviewPeriod) => {
    setPeriod(next)
    // 周期切换清日期与区间：旧窗口对新周期通常无对应记录
    setSelectedDate(null)
    setRange(null)
    setScope('current')
  }

  const changeScope = (next: TradingReviewScope) => {
    setScope(next)
    setSelectedDate(null)
  }

  const runGenerate = () => {
    const request: TradingAgentReviewGenerateRequest = { ...window, regenerate: Boolean(review) }
    generate.mutate(request, {
      onSuccess: (data) => {
        generationStartedAt.current = Date.now()
        setPendingLogId(data.logId)
        message.info('已派发复盘生成任务，完成后自动刷新')
      },
    })
  }

  const rangeWarning = range && isRangeTooLong(range[0], range[1]) ? CUSTOM_RANGE_TOO_LONG : null

  return (
    <Card
      size="small"
      title="AI 复盘"
      extra={
        <Space size="small" wrap>
          <Segmented
            size="small"
            value={range ? undefined : period}
            disabled={Boolean(range)}
            onChange={(v) => changePeriod(v as TradingReviewPeriod)}
            options={REVIEW_PERIOD_OPTIONS}
          />
          <Segmented
            size="small"
            value={scope}
            disabled={Boolean(range)}
            onChange={(v) => changeScope(v as TradingReviewScope)}
            options={SCOPE_OPTIONS}
          />
          <MarkedDatePicker
            value={selectedDate}
            onChange={setSelectedDate}
            allowClear
            size="small"
            placeholder={scope === 'previous' ? '相对最新日' : '最新一期'}
            disabled={Boolean(range)}
            markedDates={scope === 'current' ? dates?.reviewDates[period] : undefined}
          />
          <DatePicker.RangePicker
            size="small"
            value={range}
            onChange={(value) =>
              setRange(value && value[0] && value[1] ? [value[0], value[1]] : null)
            }
            allowClear
            disabledDate={(current) => current.isAfter(dayjs(), 'day')}
            placeholder={['区间开始', '区间结束']}
          />
          <Button
            size="small"
            type="primary"
            icon={<ReloadOutlined />}
            loading={generating}
            onClick={runGenerate}
          >
            {review ? '重新生成' : '生成复盘'}
          </Button>
          <Button
            size="small"
            icon={<BarChartOutlined />}
            disabled={!review}
            onClick={() => setCompareOpen(true)}
          >
            对比
          </Button>
        </Space>
      }
    >
      {rangeWarning && (
        <Alert type="warning" showIcon className="!mb-2" message={rangeWarning} />
      )}

      {isLoading ? (
        <div className="flex justify-center py-8">
          <Spin />
        </div>
      ) : !review ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={emptyDescription(period, scope, range, selectedDate?.format(DATE_FORMAT))}
        />
      ) : review.noTargetReason ? (
        <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-3">
          <div className="flex items-center gap-2">
            <Tag color="gold" className="!mr-0">
              已执行 · 无复盘对象
            </Tag>
            <span className="text-xs text-white/40">{review.tradeDate}</span>
          </div>
          <Typography.Paragraph type="secondary" className="!mb-0 mt-2 text-xs whitespace-pre-wrap">
            {review.noTargetReason}
          </Typography.Paragraph>
        </div>
      ) : (
        <Space direction="vertical" size="small" className="w-full">
          {review.metrics && <ReviewMetricsGrid metrics={review.metrics} />}

          <Descriptions size="small" column={1}>
            <Descriptions.Item label="基准日">{review.tradeDate}</Descriptions.Item>
            <Descriptions.Item label="整体">
              <Typography.Text>{review.overall}</Typography.Text>
            </Descriptions.Item>
            <Descriptions.Item label="盘面语境">
              {review.marketContext || <span className="text-white/40">无</span>}
            </Descriptions.Item>
            <Descriptions.Item label="偏差">{review.bias}</Descriptions.Item>
            <Descriptions.Item label="建议">{review.suggestion}</Descriptions.Item>
          </Descriptions>

          {review.sections.length > 0 && (
            <div className="space-y-2">
              {review.sections.map((section) => (
                <div
                  key={section.key}
                  className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2"
                >
                  <Typography.Text strong className="text-xs">
                    {section.title}
                  </Typography.Text>
                  <Typography.Paragraph className="!mb-0 mt-1 text-xs whitespace-pre-wrap" type="secondary">
                    {section.body}
                  </Typography.Paragraph>
                </div>
              ))}
            </div>
          )}

          {review.methodologyCheck.length > 0 && (
            <div>
              <Typography.Text type="secondary" className="text-xs">
                方法论验证
              </Typography.Text>
              <ul className="mt-1 space-y-1 pl-4">
                {review.methodologyCheck.map((check) => {
                  const verdict = CHECK_VERDICT_ITEMS[check.verdict] ?? {
                    label: check.verdict,
                    color: 'default',
                  }
                  return (
                    <li key={check.title}>
                      <Tag color={verdict.color}>{verdict.label}</Tag>
                      <Typography.Text strong className="text-xs">
                        {check.title}
                      </Typography.Text>
                      <Typography.Paragraph className="mb-0 text-xs" type="secondary">
                        {check.note}
                      </Typography.Paragraph>
                    </li>
                  )
                })}
              </ul>
            </div>
          )}

          {review.trades.length > 0 && (
            <Table<ApiTradingAgentTradeVerdict>
              size="small"
              rowKey="clOrdId"
              columns={verdictColumns}
              dataSource={review.trades}
              pagination={false}
              scroll={{ x: 520 }}
            />
          )}

          {review.experiences.length > 0 && (
            <div>
              <Typography.Text type="secondary" className="text-xs">
                提取经验
              </Typography.Text>
              <ul className="mt-1 space-y-1 pl-4">
                {review.experiences.map((exp) => (
                  <li key={exp.title}>
                    <Tag>{MEM_TYPE_LABELS[exp.memType] ?? exp.memType}</Tag>
                    <Typography.Text strong className="text-xs">
                      {exp.title}
                    </Typography.Text>
                    <Typography.Paragraph className="mb-0 text-xs" type="secondary">
                      {exp.body}
                    </Typography.Paragraph>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Space>
      )}

      <ReviewCompareModal
        open={compareOpen}
        onClose={() => setCompareOpen(false)}
        agentKey={agentKey}
        baseWindow={window}
      />
    </Card>
  )
}
