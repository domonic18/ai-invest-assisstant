/**
 * AI 复盘卡片（RQ-001 六档周期）：日/周/月定时生成，季/半年/年按需生成。
 *
 * 三种窗口形态与后端读取/生成同口径：本期（周期至今）、上期（上一完整周期）、
 * 自定义区间（缺 period，由后端按跨度映射报告框架）。404 = 尚未生成，
 * noTargetReason 非空 = 已执行但空仓无复盘对象（与「未生成」区分），
 * 其余错误展示真实故障并可重试。
 * 生成走异步派发（logId 轮询采集日志），完成即失效复盘/日期缓存；
 * 对比入口把当前窗口作为 A，可选 B 打开跨窗口对齐对比。
 * 状态拆分为 useReviewWindow（窗口）与 useReviewGeneration（生成状态机）。
 */
import { BarChartOutlined, ReloadOutlined } from '@ant-design/icons'
import {
  Alert,
  Button,
  Card,
  DatePicker,
  Empty,
  Segmented,
  Space,
  Spin,
} from 'antd'
import dayjs from 'dayjs'
import { useState } from 'react'

import type { TradingReviewPeriod, TradingReviewScope } from '@ai-invest/shared'

import { MarkedDatePicker } from '@/components/common/MarkedDatePicker'
import { useTradingAgentReview } from '@/hooks/useTradingAgent'
import { apiErrorMessage, apiErrorStatus } from '@/utils/errorMessage'

import { useAgentKey } from './agentKeyContext'
import { ReviewCompareModal } from './ReviewCompareModal'
import { ReviewContent } from './ReviewContent'
import { reviewEmptyDescription, REVIEW_PERIOD_OPTIONS } from './reviewMeta'
import { useReviewGeneration } from './useReviewGeneration'
import { useReviewWindow } from './useReviewWindow'

const SCOPE_OPTIONS = [
  { label: '本期', value: 'current' },
  { label: '上期', value: 'previous' },
]

export function ReviewPanel() {
  const agentKey = useAgentKey()
  const [compareOpen, setCompareOpen] = useState(false)
  const {
    period,
    scope,
    selectedDate,
    range,
    dates,
    window,
    rangeWarning,
    selectedTradeDate,
    changePeriod,
    changeScope,
    setSelectedDate,
    setRange,
  } = useReviewWindow(agentKey)
  const { data: review, isLoading, error, refetch } = useTradingAgentReview(agentKey, window)
  const { generating, runGenerate } = useReviewGeneration(agentKey, window, Boolean(review))
  // 404 = 尚未生成；其余错误是真实故障，不能伪装成空态
  const loadFailed = error != null && apiErrorStatus(error) !== 404

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

      {loadFailed ? (
        <Alert
          type="error"
          showIcon
          message="复盘加载失败"
          description={apiErrorMessage(error, '服务暂时不可用或网络异常，请稍后重试。')}
          action={
            <Button size="small" onClick={() => void refetch()}>
              重试
            </Button>
          }
        />
      ) : isLoading ? (
        <div className="flex justify-center py-8">
          <Spin />
        </div>
      ) : !review ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={reviewEmptyDescription(period, scope, Boolean(range), selectedTradeDate)}
        />
      ) : (
        <ReviewContent review={review} />
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
