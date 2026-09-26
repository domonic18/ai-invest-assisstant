/**
 * AI 复盘卡片（批次 6）：日/周/月分层复盘展示。
 *
 * 数据源为 16:10 定时任务生成的缓存（admin GET /trading-agent/review 只读，
 * 不触发 LLM）；404 表示该周期尚未生成。日期选择对齐每日复盘页
 * （MarkedDatePicker，已生成该周期复盘的基准日打点）；verdict 三层 =
 * 选股/计划/执行。
 */
import { Card, Descriptions, Empty, Segmented, Space, Spin, Table, Tag, Typography } from 'antd'
import dayjs, { type Dayjs } from 'dayjs'
import { useState } from 'react'

import type {
  ApiTradingAgentReviewExperience,
  ApiTradingAgentTradeVerdict,
  TradingReviewPeriod,
} from '@ai-invest/shared'

import { MarkedDatePicker } from '@/components/common/MarkedDatePicker'
import { useTradingAgentDates, useTradingAgentReview } from '@/hooks/useTradingAgent'
import { DATE_FORMAT } from '@/utils/formatters'

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

export function ReviewPanel() {
  const [period, setPeriod] = useState<TradingReviewPeriod>('day')
  const [selectedDate, setSelectedDate] = useState<Dayjs | null>(null)
  const tradeDate = selectedDate?.format(DATE_FORMAT)
  const { data: review, isLoading } = useTradingAgentReview(period, tradeDate)
  const { data: dates } = useTradingAgentDates()

  const changePeriod = (next: TradingReviewPeriod) => {
    setPeriod(next)
    // 周期切换清日期：旧周期的基准日对新周期通常无对应记录
    setSelectedDate(null)
  }

  return (
    <Card
      size="small"
      title="AI 复盘"
      extra={
        <Space size="small" wrap>
          <Segmented
            size="small"
            value={period}
            onChange={(v) => changePeriod(v as TradingReviewPeriod)}
            options={[
              { label: '日', value: 'day' },
              { label: '周', value: 'week' },
              { label: '月', value: 'month' },
            ]}
          />
          <MarkedDatePicker
            value={selectedDate}
            onChange={setSelectedDate}
            allowClear
            size="small"
            placeholder="最新一期"
            markedDates={dates?.reviewDates[period]}
          />
        </Space>
      }
    >
      {isLoading ? (
        <div className="flex justify-center py-8">
          <Spin />
        </div>
      ) : !review ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={
            tradeDate && dayjs(tradeDate).isBefore(dayjs(), 'day')
              ? '该日未生成此周期复盘（每交易日 16:10 盘后自动生成）'
              : '尚未生成（每交易日 16:10 盘后自动生成）'
          }
        />
      ) : (
        <Space direction="vertical" size="small" className="w-full">
          <Descriptions size="small" column={1}>
            <Descriptions.Item label="基准日">{review.tradeDate}</Descriptions.Item>
            <Descriptions.Item label="整体">
              <Typography.Text>{review.overall}</Typography.Text>
            </Descriptions.Item>
            <Descriptions.Item label="偏差">{review.bias}</Descriptions.Item>
            <Descriptions.Item label="建议">{review.suggestion}</Descriptions.Item>
          </Descriptions>

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
    </Card>
  )
}
