/**
 * 交易计划卡片（批次 7 + D28 日期语义 + D30 语义标注）：19:30 定时生成 +
 * 对话制定共用。
 *
 * 数据源 admin GET /trading-agent/plans（包装响应：tradeDate + nextTradeDate
 * + plans + executingPlanDate）。缺省显示「最近一份 ≤ 今天」的计划（计划
 * T 日制定、T+1 盘中执行，打开即正在执行/最新生成的那份）；卡片头日期轴
 * 标注制定→执行对应关系；选中无计划的日期时按 executingPlanDate 引导跳回
 * 正在执行的那份。状态分色：active 待触发 / triggered 已触发 / executed
 * 已成交 / expired 已失效 / cancelled 已取消；active 计划可人工取消。标的
 * 可点跳个股详情；sell 为持仓止损/止盈条件单（同股可与买入计划并存），
 * buy 按截至计划日持仓标注建仓/增持（heldVolume）。计划卡尾部展示当日
 * 盘中校准修正单历史（§11.5，amendments 按 planId/newPlanId 归组）。
 */
import { Button, Card, Empty, Popconfirm, Space, Spin, Tag, Typography } from 'antd'
import { StopOutlined } from '@ant-design/icons'
import dayjs, { type Dayjs } from 'dayjs'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import type { ApiTradingAgentPlan, ApiTradingAgentPlanAmendment } from '@ai-invest/shared'

import { MarkedDatePicker } from '@/components/common/MarkedDatePicker'
import { useAgentKey } from './agentKeyContext'
import {
  AMENDMENT_ACTION_META,
  AMENDMENT_STATUS_META,
  CALIBRATION_WINDOW_LABELS,
} from './calibrationMeta'
import { useCancelTradingAgentPlan, useTradingAgentDates, useTradingAgentPlans } from '@/hooks/useTradingAgent'
import { DATE_FORMAT } from '@/utils/formatters'

const STATUS_META: Record<ApiTradingAgentPlan['status'], { label: string; color: string }> = {
  active: { label: '待触发', color: 'processing' },
  triggered: { label: '已触发', color: 'warning' },
  executed: { label: '已成交', color: 'success' },
  expired: { label: '已失效', color: 'default' },
  cancelled: { label: '已取消', color: 'default' },
  invalid: { label: '计划失效', color: 'error' },
}

function fmt(value: number | null): string {
  return value != null ? value.toFixed(2) : '-'
}

// dayjs 无 zh-cn locale（仓库未启用），周X沿用手写映射惯例（TradeCalendar）
const WEEKDAY_LABELS = '日一二三四五六'

function weekdayLabel(dateStr: string): string {
  return `周${WEEKDAY_LABELS[dayjs(dateStr).day()]}`
}

function PlanRow({
  plan,
  amendments,
}: {
  plan: ApiTradingAgentPlan
  amendments: ApiTradingAgentPlanAmendment[]
}) {
  const agentKey = useAgentKey()
  const navigate = useNavigate()
  const cancel = useCancelTradingAgentPlan(agentKey)
  const status = STATUS_META[plan.status] ?? STATUS_META.expired
  const isBuy = plan.planType === 'buy'
  const held = plan.heldVolume != null && plan.heldVolume > 0

  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <Tag color={isBuy ? 'red' : 'green'} className="!mr-0">
          {isBuy ? '买入' : '止损/止盈卖出'}
        </Tag>
        <button
          type="button"
          className="min-w-0 cursor-pointer overflow-hidden text-left leading-tight"
          onClick={() => void navigate(`/stock/${plan.stockCode}`)}
        >
          <Typography.Text strong className="block truncate text-xs">
            {plan.stockName ?? plan.stockCode}
          </Typography.Text>
          <span className="block truncate font-mono text-xs text-white/50">{plan.stockCode}</span>
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
        {plan.version > 1 && (
          <Tag color="purple" className="!mr-0">
            v{plan.version}
          </Tag>
        )}
        <Tag color={status.color} className="ml-auto">
          {status.label}
        </Tag>
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
      {plan.status === 'invalid' && plan.invalidReason && (
        <div className="mt-1 text-xs text-red-400">{plan.invalidReason}</div>
      )}
      {amendments.length > 0 && (
        <div className="mt-1 space-y-1 border-t border-white/5 pt-1">
          {amendments.map((amendment, index) => {
            const action = AMENDMENT_ACTION_META[amendment.action] ?? AMENDMENT_ACTION_META.maintain
            const windowLabel =
              CALIBRATION_WINDOW_LABELS[amendment.window] ?? `校准 ${amendment.window}`
            const rejected = amendment.status === 'rejected'
            return (
              <div key={index} className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs">
                <Tag color="purple" className="!mr-0">
                  {windowLabel}
                </Tag>
                <Tag color={action.color} className="!mr-0">
                  {action.label}
                </Tag>
                {rejected && (
                  <Tag color={AMENDMENT_STATUS_META.rejected.color} className="!mr-0">
                    {AMENDMENT_STATUS_META.rejected.label}
                  </Tag>
                )}
                <span className="min-w-0 flex-1 text-gray-400">
                  {amendment.reason}
                  {rejected && amendment.rejectReason ? `（被拒：${amendment.rejectReason}）` : ''}
                </span>
              </div>
            )
          })}
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

  const amendmentsByPlan = new Map<number, ApiTradingAgentPlanAmendment[]>()
  for (const amendment of data?.amendments ?? []) {
    for (const planId of [amendment.planId, amendment.newPlanId]) {
      if (planId == null) continue
      const list = amendmentsByPlan.get(planId) ?? []
      list.push(amendment)
      amendmentsByPlan.set(planId, list)
    }
  }

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
      ) : !data ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="该日无计划（休市或未生成；每交易日 19:30 自动生成，也可在对话中制定）"
        />
      ) : data.plans.length === 0 && data.standAsideReason ? (
        <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-3">
          <div className="flex items-center gap-2">
            <Tag color="gold" className="!mr-0">
              已生成 · 空仓观望
            </Tag>
            <span className="text-xs text-white/40">{data.tradeDate}</span>
          </div>
          <Typography.Paragraph type="secondary" className="!mb-0 mt-2 text-xs whitespace-pre-wrap">
            {data.standAsideReason}
          </Typography.Paragraph>
        </div>
      ) : data.plans.length === 0 ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="该日未生成计划（每交易日 19:30 自动生成，也可在对话中制定）"
        >
          {data.executingPlanDate && (
            <Button
              type="link"
              size="small"
              className="!whitespace-normal"
              onClick={() => {
                if (data.executingPlanDate) setSelectedDate(dayjs(data.executingPlanDate))
              }}
            >
              该日盘中执行的是 {data.executingPlanDate} 制定的计划 → 查看
            </Button>
          )}
        </Empty>
      ) : (
        <Space direction="vertical" size="small" className="w-full">
          {data.nextTradeDate && (
            <div>
              {/* antd Tag 默认 nowrap，长文案窄屏溢出视口，允许折行 */}
              <Tag color="geekblue" className="!whitespace-normal">
                制定 {data.tradeDate}（{weekdayLabel(data.tradeDate)}）→ 执行{' '}
                {data.nextTradeDate}（{weekdayLabel(data.nextTradeDate)}）盘中 ·
                09:30–11:30 / 13:00–15:00
              </Tag>
            </div>
          )}
          {data.plans.map((plan) => (
            <PlanRow key={plan.id} plan={plan} amendments={amendmentsByPlan.get(plan.id) ?? []} />
          ))}
        </Space>
      )}
    </Card>
  )
}
