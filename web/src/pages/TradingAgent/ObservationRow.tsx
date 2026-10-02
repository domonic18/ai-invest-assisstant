/**
 * 观测行共享渲染（执行动态 Tab 与总览页实时决策流共用，唯一实现）。
 *
 * 行结构：时间 + 尾盘强检/计划方向 + 标的（可点跳个股详情）+ 现价/涨跌幅 +
 * 影子/动作标签 + 一句话结论 + 依据行（心跳行不渲染）+ 委托附加信息。
 * compact=false 为管理页密度（text-xs），true 为总览流密度（text-[11px]）。
 */
import { Tag, Typography } from 'antd'
import dayjs from 'dayjs'
import { useNavigate } from 'react-router-dom'

import type { ApiTradingAgentObservationItem } from '@ai-invest/shared'

import {
  ACTION_META,
  fmtConfidence,
  fmtPct,
  fmtScore,
  noulLabel,
  observationSummary,
  SUPPRESSION_META,
} from './observationMeta'
import { changeHex } from '@/utils/formatters'

interface Density {
  row: string
  time: string
  summary: string
  evidence: string
  evidenceLabel: string
  evidenceModel: string
  footer: string
  orderVolume: string
  clOrdId: string
}

const DENSITY: Record<'full' | 'compact', Density> = {
  full: {
    row: 'px-3 py-2',
    time: 'font-mono text-xs text-white/50',
    summary: 'mt-0.5 text-xs',
    evidence: 'mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-gray-400',
    evidenceLabel: 'text-gray-500',
    evidenceModel: 'font-mono text-gray-500',
    footer: 'mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs',
    orderVolume: 'text-gray-400',
    clOrdId: 'font-mono text-gray-500',
  },
  compact: {
    row: 'px-3 py-1.5',
    time: 'font-mono text-[11px] text-white/45',
    summary: 'mt-0.5 text-[11px]',
    evidence: 'mt-0.5 flex flex-wrap items-center gap-x-2.5 gap-y-0.5 text-[11px] text-white/35',
    evidenceLabel: 'text-white/30',
    evidenceModel: 'font-mono text-white/25',
    footer: 'mt-0.5 flex flex-wrap items-center gap-x-2.5 gap-y-0.5 text-[11px]',
    orderVolume: 'text-white/40',
    clOrdId: 'font-mono text-white/35',
  },
}

/** 依据行（模型三题答案 + 模型版本；心跳行无 choice 不渲染）。 */
function EvidenceLine({ item, d }: { item: ApiTradingAgentObservationItem; d: Density }) {
  const decision = item.decision
  if (!decision?.choice) return null
  const parts: string[] = []
  if (decision.confidence != null) parts.push(fmtConfidence(decision.confidence))
  if (decision.score != null) parts.push(`盘面 ${fmtScore(decision.score)}`)
  if (decision.noul != null) parts.push(noulLabel(decision.noul, item.planType))
  return (
    <div className={d.evidence}>
      <span className={d.evidenceLabel}>依据</span>
      {parts.map((part) => (
        <span key={part}>{part}</span>
      ))}
      {decision.servedModel && <span className={d.evidenceModel}>{decision.servedModel}</span>}
    </div>
  )
}

export function ObservationRow({
  item,
  compact = false,
  animate = false,
}: {
  item: ApiTradingAgentObservationItem
  /** true = 总览决策流密度（text-[11px]）；false = 执行动态管理密度（text-xs） */
  compact?: boolean
  /** 挂载滑入动画（实时流新行用，prefers-reduced-motion 时由调用方关掉） */
  animate?: boolean
}) {
  const navigate = useNavigate()
  const d = DENSITY[compact ? 'compact' : 'full']
  const isTail = item.decision?.window === 'tail_check'
  const action = item.action ? (ACTION_META[item.action] ?? null) : null
  const suppression = item.suppressionReason
    ? SUPPRESSION_META[item.suppressionReason] ?? item.suppressionReason
    : null
  const heartbeat = item.l0Verdict === 'no_action' && !item.action

  return (
    <div
      className={`rounded-lg border border-white/10 bg-white/[0.03] ${d.row} ${
        heartbeat ? 'opacity-40' : ''
      } ${animate ? 'animate-[feed-row-in_0.35s_ease-out]' : ''}`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className={d.time}>{dayjs(item.tickTime).format('HH:mm:ss')}</span>
        {isTail ? (
          <>
            <Tag color="geekblue" className="!mr-0">
              尾盘强检
            </Tag>
            <span className={`font-mono text-xs text-white/45`}>{item.stockCode}</span>
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
              <Typography.Text strong className="block truncate text-xs">
                {item.stockName ?? item.stockCode}
              </Typography.Text>
              <span className="block truncate font-mono text-xs text-white/40">
                {item.stockCode}
              </span>
            </button>
          </>
        )}
        {item.price != null && (
          <span className="font-mono text-xs">
            <span className="text-white/70">{item.price.toFixed(2)}</span>{' '}
            <span style={{ color: changeHex(item.changePct) }}>{fmtPct(item.changePct)}</span>
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
      <div className={`${d.summary} ${heartbeat ? 'text-white/40' : 'text-white/75'}`}>
        {observationSummary(item)}
      </div>
      <EvidenceLine item={item} d={d} />
      {(suppression || item.clOrdId || item.orderVolume != null) && (
        <div className={d.footer}>
          {suppression && <Tag color="warning">{suppression}</Tag>}
          {item.orderVolume != null && (
            <span className={d.orderVolume}>
              {item.planType === 'sell' ? '卖出' : '买入'} {item.orderVolume} 股
            </span>
          )}
          {item.clOrdId && <span className={d.clOrdId}>委托号 {item.clOrdId}</span>}
        </div>
      )}
    </div>
  )
}
