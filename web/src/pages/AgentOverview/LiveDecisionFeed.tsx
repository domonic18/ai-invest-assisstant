/**
 * 实时决策流面板（Agent Hub 总览页）：盘中逐 tick 观测滚动流，mission-control
 * 风格。展示舞台点选的 agent（selectedKey），未选中时回退首个 active agent。
 * 全部逐 tick（含无动作心跳行，弱化显示；显著事件高亮）。盘中
 * （marketSession open）15s 快轮询，新行以 item.id 为 React key 挂载触发
 * 滑入动画；非盘中降为 60s 慢轮询并显示「回顾」badge（badge 求值在渲染期，
 * 切换滞后 ≤1 轮询周期）。无 agent 可展示时整体隐藏。
 */
import { Empty, Spin, Tag } from 'antd'
import dayjs from 'dayjs'
import { Link, useNavigate } from 'react-router-dom'

import type {
  AgentOverviewItem,
  ApiTradingAgentObservationItem,
  ApiTradingAgentObservationSummary,
} from '@ai-invest/shared'

import { useLiveAgentObservations } from '@/hooks/useTradingAgent'
import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion'
import { marketSession } from '@/pages/PaperTrade/tradingRules'
import type { MarketSession } from '@/pages/PaperTrade/tradingRules'
import {
  ACTION_META,
  fmtConfidence,
  fmtPct,
  fmtScore,
  noulLabel,
  observationSummary,
  SUPPRESSION_META,
} from '@/pages/TradingAgent/observationMeta'
import { ObservationLegend } from '@/pages/TradingAgent/observationLegend'
import { changeColor } from '@/utils/formatters'

const FEED_ROW_KEYFRAMES = `
@keyframes feed-row-in {
  from { opacity: 0; transform: translateY(-6px); }
  to { opacity: 1; transform: none; }
}
`

/** 会话 badge：盘中绿点脉冲「实时」，午休琥珀，其余灰「回顾」最近观测日。 */
function SessionBadge({ session, reviewDate }: { session: MarketSession; reviewDate?: string }) {
  if (session === 'open') {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs font-medium text-emerald-400">
        <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400" />
        实时
      </span>
    )
  }
  if (session === 'break') {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs font-medium text-amber-400">
        <span className="h-2 w-2 rounded-full bg-amber-400" />
        午间休市
      </span>
    )
  }
  const label = session === 'pre' ? '待开盘' : '已收盘'
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-white/40">
      <span className="h-2 w-2 rounded-full bg-white/30" />
      {label}
      {reviewDate && <span className="font-mono">· 回顾 {reviewDate}</span>}
    </span>
  )
}

/** 依据行（模型三题答案 + 模型版本；心跳行无 choice 不渲染）。 */
function EvidenceLine({ item }: { item: ApiTradingAgentObservationItem }) {
  const decision = item.decision
  if (!decision?.choice) return null
  const parts: string[] = []
  if (decision.confidence != null) parts.push(fmtConfidence(decision.confidence))
  if (decision.score != null) parts.push(`盘面 ${fmtScore(decision.score)}`)
  if (decision.noul != null) parts.push(noulLabel(decision.noul, item.planType))
  return (
    <div className="mt-0.5 flex flex-wrap items-center gap-x-2.5 text-[11px] text-white/35">
      <span className="text-white/30">依据</span>
      {parts.map((part) => (
        <span key={part}>{part}</span>
      ))}
      {decision.servedModel && (
        <span className="font-mono text-white/25">{decision.servedModel}</span>
      )}
    </div>
  )
}

function FeedRow({ item, animate }: { item: ApiTradingAgentObservationItem; animate: boolean }) {
  const navigate = useNavigate()
  const isTail = item.decision?.window === 'tail_check'
  const action = item.action ? (ACTION_META[item.action] ?? null) : null
  const suppression = item.suppressionReason
    ? SUPPRESSION_META[item.suppressionReason] ?? item.suppressionReason
    : null
  const heartbeat = item.l0Verdict === 'no_action' && !item.action

  return (
    <div
      className={`rounded-lg border border-white/10 bg-white/[0.03] px-3 py-1.5 ${
        heartbeat ? 'opacity-40' : ''
      } ${animate ? 'animate-[feed-row-in_0.35s_ease-out]' : ''}`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-[11px] text-white/45">
          {dayjs(item.tickTime).format('HH:mm:ss')}
        </span>
        {isTail ? (
          <>
            <Tag color="geekblue" className="!mr-0">
              尾盘强检
            </Tag>
            <span className="font-mono text-[11px] text-white/45">{item.stockCode}</span>
          </>
        ) : (
          <>
            {item.planType && (
              <Tag color={item.planType === 'buy' ? 'red' : 'green'} className="!mr-0">
                {item.planType === 'buy' ? '买入' : '卖出'}
              </Tag>
            )}
            <button
              type="button"
              className="min-w-0 cursor-pointer overflow-hidden text-left leading-tight"
              onClick={() => void navigate(`/stock/${item.stockCode}`)}
            >
              <span className="block truncate text-[11px] text-white/85">
                {item.stockName ?? item.stockCode}
              </span>
              <span className="block truncate font-mono text-[11px] text-white/40">
                {item.stockCode}
              </span>
            </button>
          </>
        )}
        {item.price != null && (
          <span className="font-mono text-[11px]">
            <span className="text-white/70">{item.price.toFixed(2)}</span>{' '}
            <span className={changeColor(item.changePct)}>{fmtPct(item.changePct)}</span>
          </span>
        )}
        <span className="ml-auto" />
        {item.isShadow && (
          <Tag color="gold" className="!mr-0">
            影子
          </Tag>
        )}
        {action && <Tag color={action.color}>{action.label}</Tag>}
      </div>
      <div className={`mt-0.5 text-[11px] ${heartbeat ? 'text-white/40' : 'text-white/75'}`}>
        {observationSummary(item)}
      </div>
      <EvidenceLine item={item} />
      {(suppression || item.clOrdId || item.orderVolume != null) && (
        <div className="mt-0.5 flex flex-wrap items-center gap-x-2.5 text-[11px]">
          {suppression && <Tag color="warning">{suppression}</Tag>}
          {item.orderVolume != null && (
            <span className="text-white/40">
              {item.planType === 'sell' ? '卖出' : '买入'} {item.orderVolume} 股
            </span>
          )}
          {item.clOrdId && <span className="font-mono text-white/35">委托号 {item.clOrdId}</span>}
        </div>
      )}
    </div>
  )
}

function StatsChip({ summary }: { summary: ApiTradingAgentObservationSummary }) {
  return (
    <span className="font-mono text-[11px] text-white/35">
      tick {summary.totalTicks} · 显著 {summary.significantTicks}
    </span>
  )
}

export function LiveDecisionFeed({
  items,
  isLoading,
  selectedKey,
}: {
  items: AgentOverviewItem[]
  isLoading: boolean
  /** 舞台点选的 agentKey；空/未知时回退首个 active agent。 */
  selectedKey?: string | null
}) {
  const reducedMotion = usePrefersReducedMotion()
  const agent =
    items.find(
      (item) => item.profile.agentKey === selectedKey && item.runtimeState !== 'off',
    ) ??
    items.find((item) => item.profile.status === 'active') ??
    null
  const { data, isLoading: feedLoading } = useLiveAgentObservations(
    agent?.profile.agentKey ?? null,
  )

  if (isLoading || !agent) return null

  const session = marketSession()

  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03]">
      <style>{FEED_ROW_KEYFRAMES}</style>
      <div className="flex flex-wrap items-center gap-2 px-4 pt-3">
        <span className="text-sm font-medium text-white/85">实时决策流</span>
        <SessionBadge session={session} reviewDate={data?.tradeDate} />
        <span className="ml-auto" />
        <Link
          to={`/trading-agent/${agent.profile.agentKey}`}
          className="text-xs text-sky-400/80 transition-colors hover:text-sky-300"
        >
          {agent.profile.name}
        </Link>
        {data && <StatsChip summary={data.summary} />}
        <ObservationLegend />
      </div>
      <div className="h-[280px] overflow-y-auto px-4 pb-3 pt-2">
        {feedLoading && !data ? (
          <div className="flex justify-center py-10">
            <Spin size="small" />
          </div>
        ) : !data || data.items.length === 0 ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无观测留痕" />
        ) : (
          <div className="flex flex-col gap-1.5">
            {data.items.map((item) => (
              <FeedRow key={item.id} item={item} animate={!reducedMotion} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
