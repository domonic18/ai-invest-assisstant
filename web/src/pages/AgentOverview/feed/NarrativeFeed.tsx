/**
 * 拟人化实时决策流（右栏，~380px）：叙事化卡片（一句人话 + 弱化 mono 附注），
 * 卡片左边线 = 事件色（执行红/校准绿/其余身份色），头像 = 芯片方块。
 * 数据源：选中芯片 agent 的逐 tick 观测（useLiveAgentObservations，盘中 15s）。
 */
import { Empty, Spin } from 'antd'
import { Link } from 'react-router-dom'

import type {
  AgentOverviewItem,
  ApiTradingAgentObservationPage,
} from '@ai-invest/shared'

import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion'
import { marketSession } from '@/pages/PaperTrade/tradingRules'
import { bjNow } from '@/utils/beijing'

import { BOARD, MONO } from '../circuit/boardTheme'

import { toNarrative } from './narrative'

import type { NarrativeCard } from './narrative'

/** 右栏最多渲染的卡片数：整页约束在一屏内，更早的观测去 Agent 详情页看。 */
const MAX_FEED_CARDS = 8

interface FeedEntry {
  card: NarrativeCard
  /** 与上一条同股同事件的连续重复次数（+N 徽标，0 = 无合并） */
  repeat: number
}

/** 连续重复条目合并：同股同 tag 刷屏（心跳/观望）只保留最新一条并累计 +N。 */
function mergeRuns(cards: NarrativeCard[]): FeedEntry[] {
  const entries: FeedEntry[] = []
  for (const card of cards) {
    const last = entries[entries.length - 1]
    if (last && last.card.stockCode === card.stockCode && last.card.tag === card.tag) {
      last.repeat += 1
      last.card = card
    } else {
      entries.push({ card, repeat: 0 })
    }
  }
  return entries
}

const TONE_STYLE: Record<NarrativeCard['tone'], { border: string; bg: string; text: string; tagBg: string; tagText: string }> = {
  hot: {
    border: BOARD.red,
    bg: 'rgba(248,81,73,.06)',
    text: BOARD.redPale,
    tagBg: 'rgba(248,81,73,.16)',
    tagText: BOARD.redPale,
  },
  dim: {
    border: BOARD.lineSoft,
    bg: BOARD.card,
    text: BOARD.textMid,
    tagBg: 'rgba(140,140,140,.12)',
    tagText: BOARD.textMid,
  },
  norm: {
    border: BOARD.lineSoft,
    bg: BOARD.card,
    text: '#d7dce5',
    tagBg: 'rgba(140,140,140,.12)',
    tagText: BOARD.textMid,
  },
}

function ChipAvatar({ accent }: { accent: string }) {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" className="mt-0.5 flex-none">
      <rect x="5" y="5" width="14" height="14" rx="3" fill="none" stroke={accent} strokeWidth="1.2" />
      <rect x="9.5" y="9.5" width="5" height="5" fill={accent} />
    </svg>
  )
}

function SessionPill({ session }: { session: 'open' | 'break' | 'pre' | 'closed' }) {
  const meta = {
    open: { text: `盘中 · ${bjNow().format('HH:mm')}`, color: BOARD.greenText, border: 'rgba(46,160,67,.3)', bg: 'rgba(46,160,67,.10)' },
    break: { text: '午间休市', color: BOARD.amberSoft, border: 'rgba(210,153,34,.3)', bg: 'rgba(210,153,34,.10)' },
    pre: { text: '待开盘', color: BOARD.textMid, border: 'rgba(140,140,140,.25)', bg: 'rgba(140,140,140,.08)' },
    closed: { text: '已收盘', color: BOARD.textMid, border: 'rgba(140,140,140,.25)', bg: 'rgba(140,140,140,.08)' },
  }[session]
  return (
    <span
      className="rounded-full border px-2 py-px text-[11px]"
      style={{ color: meta.color, borderColor: meta.border, backgroundColor: meta.bg }}
    >
      {meta.text}
    </span>
  )
}

export function NarrativeFeed({
  agent,
  feed,
  feedLoading,
}: {
  /** 已解析的展示 agent（选中非 off 回退首个 active），null = 无 agent 可展示。 */
  agent: AgentOverviewItem | null
  feed: ApiTradingAgentObservationPage | undefined
  feedLoading: boolean
}) {
  const reducedMotion = usePrefersReducedMotion()
  if (!agent) return null
  const accent = agent.profile.accentColor ?? BOARD.cyan
  const cards = mergeRuns((feed?.items ?? []).slice(0, MAX_FEED_CARDS).map(toNarrative))
  const session = marketSession()

  return (
    <div
      className={`flex w-full flex-none flex-col gap-2.5 overflow-hidden rounded-2xl border border-[#23262d] bg-[#111318] p-3.5 lg:w-[380px] ${reducedMotion ? 'ahc-reduced' : ''}`}
    >
      <style>{`.ahc-feed-card { animation: ahc-feedin .5s ease both; } @keyframes ahc-feedin { from{opacity:0; transform:translateY(-8px)} to{opacity:1; transform:none} }`}</style>
      <div className="flex items-center gap-2">
        <ChipAvatar accent={accent} />
        <span className="text-[14.5px] font-semibold text-[#f0f1f5]">实时决策流</span>
        <span
          className="rounded-full border px-2 py-px text-[11.5px]"
          style={{ color: BOARD.cyanSoft, borderColor: 'rgba(34,211,238,.35)', backgroundColor: 'rgba(34,211,238,.08)' }}
        >
          <Link to={`/trading-agent/${agent.profile.agentKey}`} style={{ color: 'inherit' }}>
            {agent.profile.name} · {agent.stateLabel ?? '待命'}
          </Link>
        </span>
        <span className="ml-auto">
          <SessionPill session={session} />
        </span>
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto">
        {feedLoading && !feed ? (
          <div className="flex justify-center py-10">
            <Spin size="small" />
          </div>
        ) : cards.length === 0 ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无观测留痕" />
        ) : (
          cards.map(({ card, repeat }) => {
            const tone = TONE_STYLE[card.tone]
            const borderColor = card.tone === 'hot' ? tone.border : accent
            return (
              <div
                key={card.key}
                className="ahc-feed-card flex gap-2 rounded-xl border border-l-[3px] px-2.5 py-1.5 pr-3"
                style={{ backgroundColor: tone.bg, borderColor: tone.border, borderLeftColor: borderColor }}
              >
                <ChipAvatar accent={accent} />
                <div className="min-w-0">
                  <div className="flex items-baseline gap-2">
                    <span className="text-[10px]" style={{ color: BOARD.grey, fontFamily: MONO }}>
                      {card.time}
                    </span>
                    <span
                      className="rounded-full px-1.5 text-[9.5px]"
                      style={{ backgroundColor: tone.tagBg, color: tone.tagText }}
                    >
                      {card.tag}
                    </span>
                    {repeat > 0 && (
                      <span className="text-[9.5px]" style={{ color: BOARD.grey, fontFamily: MONO }}>
                        +{repeat}
                      </span>
                    )}
                  </div>
                  <div className="text-[12px] leading-snug" style={{ color: tone.text, fontWeight: card.tone === 'hot' ? 600 : 400 }}>
                    {card.sentence}
                  </div>
                  <div className="mt-0.5 text-[10px]" style={{ color: BOARD.grey, fontFamily: MONO }}>
                    {card.meta}
                  </div>
                </div>
              </div>
            )
          })
        )}
      </div>

      {session === 'open' && (
        <div className="ahc-typing flex gap-1.5 pl-0.5 pt-1">
          {[0, 1, 2].map((i) => (
            <i key={i} className="block h-1.5 w-1.5 rounded-full bg-[#2e323c]" />
          ))}
        </div>
      )}
    </div>
  )
}
