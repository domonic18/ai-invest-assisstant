/**
 * 实时决策流面板（Agent Hub 总览页）：盘中逐 tick 观测滚动流，mission-control
 * 风格。展示舞台点选的 agent（selectedKey），未选中时回退首个 active agent。
 * 全部逐 tick（含无动作心跳行，弱化显示；显著事件高亮）。盘中
 * （marketSession open）15s 快轮询，新行以 item.id 为 React key 挂载触发
 * 滑入动画；非盘中降为 60s 慢轮询并显示「回顾」badge（badge 求值在渲染期，
 * 切换滞后 ≤1 轮询周期）。无 agent 可展示时整体隐藏。
 *
 * 行渲染复用 TradingAgent/ObservationRow（compact 密度），本文件只保留
 * 面板壳、会话 badge 与统计 chip。
 */
import { Empty, Spin } from 'antd'
import { Link } from 'react-router-dom'

import type {
  AgentOverviewItem,
  ApiTradingAgentObservationSummary,
} from '@ai-invest/shared'

import { useLiveAgentObservations } from '@/hooks/useTradingAgent'
import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion'
import { marketSession } from '@/pages/PaperTrade/tradingRules'
import type { MarketSession } from '@/pages/PaperTrade/tradingRules'
import { ObservationLegend } from '@/pages/TradingAgent/observationLegend'
import { ObservationRow } from '@/pages/TradingAgent/ObservationRow'

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
              <ObservationRow key={item.id} item={item} compact animate={!reducedMotion} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
