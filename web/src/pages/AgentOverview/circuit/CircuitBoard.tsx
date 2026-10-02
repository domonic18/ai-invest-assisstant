/**
 * 电路脉冲主板（智能中枢左画布，REV4）：PCB 底板 + 走线层 + 主控 + Agent 芯片列
 * + 外设心跳 + 逻辑分析仪 + 丝印。SVG viewBox 1140×800，在弹性容器内等比
 * 缩放，高度由页面一屏约束驱动；fillWidth（决策流收起）时改为宽度铺满、
 * 超出容器高度部分纵向滚动。
 * 点击芯片联动右栏决策流（selectedKey）。
 */
import type { AgentOverviewItem } from '@ai-invest/shared'

import type { CeleryQueues, SystemStatus } from '@ai-invest/shared'

import { BOARD, BOARD_CSS, chipSlotY } from './boardTheme'
import { AgentChips } from './AgentChips'
import { LogicAnalyzer } from './LogicAnalyzer'
import { MainChip } from './MainChip'
import type { LatestOrder } from './Peripherals'
import { Peripherals } from './Peripherals'
import { StateLegend } from './StateLegend'
import { TraceLayer } from './TraceLayer'

function hexWithAlpha(hex: string, alpha: string): string {
  return `${hex}${alpha}`
}

function BoardDefs({ items }: { items: AgentOverviewItem[] }) {
  return (
    <defs>
      {items.map((item, i) => {
        const accent = item.profile.accentColor ?? BOARD.cyan
        return (
          <radialGradient key={item.profile.agentKey} id={`ahc-die-${i}`} cx="50%" cy="50%" r="55%">
            <stop offset="0%" stopColor={hexWithAlpha(accent, 'd9')} />
            <stop offset="100%" stopColor={hexWithAlpha(accent, '00')} />
          </radialGradient>
        )
      })}
      <radialGradient id="ahc-dieGreen" cx="50%" cy="50%" r="55%">
        <stop offset="0%" stopColor="rgba(52,211,153,.8)" />
        <stop offset="100%" stopColor="rgba(52,211,153,0)" />
      </radialGradient>
      <linearGradient id="ahc-histTrail" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0%" stopColor="rgba(165,243,252,0)" />
        <stop offset="100%" stopColor="rgba(165,243,252,.14)" />
      </linearGradient>
      <filter id="ahc-softC" x="-80%" y="-80%" width="260%" height="260%">
        <feGaussianBlur stdDeviation="4" />
      </filter>
      <pattern id="ahc-solder" width="46" height="46" patternUnits="userSpaceOnUse">
        <circle cx="23" cy="23" r="1" fill="rgba(52,211,153,.09)" />
      </pattern>
    </defs>
  )
}

export function CircuitBoard({
  items,
  selectedKey,
  onSelectAgent,
  systemStatus,
  celeryQueues,
  latestOrder,
  today,
  nowMinutes,
  reducedMotion,
  fillWidth = false,
}: {
  items: AgentOverviewItem[]
  selectedKey: string | null
  onSelectAgent: (agentKey: string) => void
  systemStatus: SystemStatus | undefined
  celeryQueues: CeleryQueues | undefined
  latestOrder: (LatestOrder & { agentKey: string }) | null
  today: string
  nowMinutes: number
  reducedMotion: boolean
  /** 决策流收起（整屏模式）：按宽度铺满放大，容器内纵向滚动；默认按高度适配一屏。 */
  fillWidth?: boolean
}) {
  const chipTargets = items.map((item, i) => ({
    y: chipSlotY(i),
    enabled: item.runtimeState !== 'off',
    accent: item.profile.accentColor ?? BOARD.cyan,
    hasOrders: item.orderCount > 0,
  }))

  return (
    <div
      className={`min-h-0 flex-1 rounded-[18px] border border-[#23262d] bg-[#0a0f0d] shadow-[0_24px_70px_rgba(0,0,0,.6)] ${fillWidth ? 'overflow-y-auto' : 'overflow-hidden'} ${reducedMotion ? 'ahc-reduced' : ''}`}
    >
      <style>{BOARD_CSS}</style>
      <svg
        viewBox="0 0 1140 800"
        preserveAspectRatio="xMidYMid meet"
        className={fillWidth ? 'mx-auto block w-full' : 'mx-auto block h-full max-h-full w-auto max-w-full'}
        role="img"
        aria-label="智能中枢电路主板"
      >
        <BoardDefs items={items} />
        <rect width="1140" height="800" fill={BOARD.bg} />
        <rect width="1140" height="800" fill="url(#ahc-solder)" />
        {/* PCB 边框 + 固定孔 */}
        <rect x="18" y="18" width="1104" height="764" rx="14" fill="none" stroke={BOARD.pcbEdge} strokeWidth="2" />
        <rect x="26" y="26" width="1088" height="748" rx="10" fill="none" stroke={BOARD.pcbEdgeSoft} strokeWidth="1" />
        <g fill="none" stroke="rgba(52,211,153,.3)" strokeWidth="1.4">
          <circle cx="52" cy="52" r="9" />
          <circle cx="1088" cy="52" r="9" />
          <circle cx="52" cy="748" r="9" />
          <circle cx="1088" cy="748" r="9" />
        </g>
        <g fill="none" stroke="rgba(52,211,153,.18)" strokeWidth="1">
          <circle cx="52" cy="52" r="4" />
          <circle cx="1088" cy="52" r="4" />
          <circle cx="52" cy="748" r="4" />
          <circle cx="1088" cy="748" r="4" />
        </g>

        <TraceLayer chips={chipTargets} reducedMotion={reducedMotion} />
        <MainChip />
        <StateLegend />
        <AgentChips items={items} selectedKey={selectedKey} onSelectAgent={onSelectAgent} />
        <Peripherals
          systemStatus={systemStatus}
          celeryQueues={celeryQueues}
          latestOrder={latestOrder}
          today={today}
          reducedMotion={reducedMotion}
        />
        <LogicAnalyzer items={items} latestOrder={latestOrder} nowMinutes={nowMinutes} reducedMotion={reducedMotion} />

        {/* 板号丝印 */}
        <text x="60" y="770" fontSize="9" fill={BOARD.silk} letterSpacing="2" style={{ fontFamily: 'monospace' }}>
          AI-INVEST MAINBOARD · REV 4.0
        </text>
        <text x="1080" y="770" fontSize="9" fill={BOARD.silk} textAnchor="end" style={{ fontFamily: 'monospace' }}>
          PWR OK · 3.3V/1.8V/0.9V
        </text>
      </svg>
    </div>
  )
}
