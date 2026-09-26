/**
 * 交易计划卡片（批次 7 + D28 日期语义 + D30 语义标注）：19:30 定时生成 +
 * 对话制定共用。
 *
 * 数据源 admin GET /trading-agent/plans（包装响应：tradeDate + nextTradeDate
 * + plans）；标题显示所选日期，徽标注明计划于下一交易日盘中执行与交易时段；
 * 日期选择对齐每日复盘页（MarkedDatePicker，有计划的日期打点）；状态分色：
 * active 待触发 / triggered 已触发 / executed 已成交 / expired 已失效 /
 * cancelled 已取消；active 计划可人工取消。标的可点跳个股详情；sell 为
 * 持仓止损/止盈条件单（同股可与买入计划并存），buy 按截至计划日持仓标注
 * 建仓/增持（heldVolume）。
 */
import { Card, Empty, Popconfirm, Space, Spin, Tag, Typography } from 'antd'
import { StopOutlined } from '@ant-design/icons'
import type { Dayjs } from 'dayjs'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import type { ApiTradingAgentPlan } from '@ai-invest/shared'

import { MarkedDatePicker } from '@/components/common/MarkedDatePicker'
import { useAgentKey } from './agentKeyContext'
import { useCancelTradingAgentPlan, useTradingAgentDates, useTradingAgentPlans } from '@/hooks/useTradingAgent'
import { DATE_FORMAT } from '@/utils/formatters'

const STATUS_META: Record<ApiTradingAgentPlan['status'], { label: string; color: string }> = {
  active: { label: '待触发', color: 'processing' },
  triggered: { label: '已触发', color: 'warning' },
  executed: { label: '已成交', color: 'success' },
  expired: { label: '已失效', color: 'default' },
  cancelled: { label: '已取消', color: 'default' },
}

function fmt(value: number | null): string {
  return value != null ? value.toFixed(2) : '-'
}

function PlanRow({ plan }: { plan: ApiTradingAgentPlan }) {
  const agentKey = useAgentKey()
  const navigate = useNavigate()
  const cancel = useCancelTradingAgentPlan(agentKey)
  const status = STATUS_META[plan.status] ?? STATUS_META.expired
  const isBuy = plan.planType === 'buy'
  const held = plan.heldVolume != null && plan.heldVolume > 0

  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">
      <div className="flex items-center gap-2">
        <Tag color={isBuy ? 'red' : 'green'} className="!mr-0">
          {isBuy ? '买入' : '止损/止盈卖出'}
        </Tag>
        <button
          type="button"
          className="min-w-0 cursor-pointer text-left leading-tight"
          onClick={() => void navigate(`/stock/${plan.stockCode}`)}
        >
          <Typography.Text strong className="block truncate text-xs">
            {plan.stockName ?? plan.stockCode}
          </Typography.Text>
          <span className="font-mono text-xs text-white/50">{plan.stockCode}</span>
        </button>
        {isBuy ? (
          <Tag color="gold" className="!mr-0">
            {held ? '增持' : '建仓'}
            {held ? ` · 持仓 ${plan.heldVolume} 股` : ''}
          </Tag>
        ) : held ? (
          <Tag color="gold" className="!mr-0">
            持仓 {plan.heldVolume} 股
          </Tag>
        ) : null}
        <span className="ml-auto" />
        <Tag color={status.color}>{status.label}</Tag>
        {plan.status === 'active' && (
          <Popconfirm
            title="取消该计划"
            description="取消后盘中执行器不再消费此计划。"
            okText="取消计划"
            cancelText="返回"
            onConfirm={() => cancel.mutate(plan.id)}
          >
            <StopOutlined className="text-gray-500 hover:text-gray-300" />
          </Popconfirm>
        )}
      </div>
      <div className="mt-1 text-xs text-gray-300">{plan.strategy}</div>
      <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-gray-500 font-mono">
        {isBuy && (
          <span>
            买点区间 {fmt(plan.buyZoneLow)} ~ {fmt(plan.buyZoneHigh)}
          </span>
        )}
        {!isBuy && <span>止盈 {fmt(plan.targetPrice)}</span>}
        <span className="text-gray-400">止损 {fmt(plan.stopLoss)}</span>
        <span>仓位 {plan.positionPct.toFixed(0)}%</span>
      </div>
      <Typography.Paragraph type="secondary" className="!mb-0 mt-1 text-xs" ellipsis={{ rows: 2 }}>
        {plan.basis}
      </Typography.Paragraph>
      {plan.triggeredClOrdId && (
        <div className="mt-1 text-xs text-gray-500 font-mono">
          委托号 {plan.triggeredClOrdId}
        </div>
      )}
    </div>
  )
}

export function PlanPanel() {
  const agentKey = useAgentKey()
  const [selectedDate, setSelectedDate] = useState<Dayjs | null>(null)
  const tradeDate = selectedDate?.format(DATE_FORMAT)
  const { data, isLoading } = useTradingAgentPlans(agentKey, tradeDate)
  const { data: dates } = useTradingAgentDates(agentKey)

  const shownDate = tradeDate ?? data?.tradeDate
  const title = shownDate ? `${shownDate} 交易计划` : '交易计划'

  return (
    <Card
      size="small"
      title={title}
      extra={
        <MarkedDatePicker
          value={selectedDate}
          onChange={setSelectedDate}
          allowClear
          size="small"
          placeholder="最近交易日"
          markedDates={dates?.planDates}
        />
      }
    >
      {isLoading ? (
        <div className="flex justify-center py-8">
          <Spin />
        </div>
      ) : !data || data.plans.length === 0 ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="该日无计划（休市或未生成；每交易日 19:30 自动生成，也可在对话中制定）"
        />
      ) : (
        <Space direction="vertical" size="small" className="w-full">
          {data.nextTradeDate && (
            <div>
              <Tag color="geekblue">
                下一交易日 {data.nextTradeDate} 盘中执行 · 09:30–11:30 / 13:00–15:00
              </Tag>
            </div>
          )}
          {data.plans.map((plan) => (
            <PlanRow key={plan.id} plan={plan} />
          ))}
        </Space>
      )}
    </Card>
  )
}
