/**
 * Agent 芯片列（右列三槽位 + 顺延）：五态渲染（工作/已产出/待机/暂停/空插槽），
 * 身份色 = profile.accentColor，状态由 LED 编排 + 呼吸节奏 + 文字标签表达。
 * 点击芯片 → 右栏决策流过滤（selectedKey）；选中态 = 四角锁定框。
 */
import type { AgentOverviewItem } from '@ai-invest/shared'

import { BOARD, chipSlotY, MONO } from './boardTheme'
import { deriveChipVisual } from './chipState'

function Led({
  x,
  y,
  color,
  visual,
  index,
}: {
  x: number
  y: number
  color: string
  visual: ReturnType<typeof deriveChipVisual>
  index: number
}) {
  if (visual.led === 'none') return null
  if (visual.led === 'chase') {
    return <circle cx={x} cy={y} r="2.6" fill={color} className={`ahc-led${index + 1}`} />
  }
  if (visual.led === 'solid') {
    return <circle cx={x} cy={y} r="2.6" fill={index === 0 ? color : `${color}26`} />
  }
  return (
    <circle
      cx={x}
      cy={y}
      r="2.6"
      fill={index === 0 ? color : `${color}26`}
      className={index === 0 ? 'ahc-corebeat-slow' : undefined}
    />
  )
}

function Reticle({ y, color }: { y: number; color: string }) {
  const x = 810
  const w = 140
  const h = 104
  const c = 12
  const d = `M${x} ${y - 10 + c} V${y - 10} H${x + c} M${x + w - c} ${y - 10} H${x + w} V${y - 10 + c} M${x + w} ${y - 10 + h - c} V${y - 10 + h} H${x + w - c} M${x + c} ${y - 10 + h} H${x} V${y - 10 + h - c}`
  return <path d={d} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" />
}

function AgentChip({
  item,
  index,
  selected,
  onSelect,
}: {
  item: AgentOverviewItem
  index: number
  selected: boolean
  onSelect: (agentKey: string) => void
}) {
  const y = chipSlotY(index)
  const { profile } = item
  const accent = profile.accentColor ?? BOARD.cyan
  const visual = deriveChipVisual(item)
  const ledColor = visual.ledColorOverride ?? accent

  if (visual.mode === 'off') {
    return (
      <g onClick={() => onSelect(profile.agentKey)} cursor="pointer" role="button" aria-label={profile.name}>
        <title>{profile.name}</title>
        {selected && <Reticle y={y} color={BOARD.greySoft} />}
        <text x="910" y={y - 8} textAnchor="middle" fontSize="8" fill="#3f4653" letterSpacing="1" style={{ fontFamily: MONO }}>
          {visual.codeText}
        </text>
        <rect x="850" y={y} width="120" height="84" rx="8" fill="none" stroke="rgba(148,163,184,.35)" strokeWidth="1.4" strokeDasharray="5 4" />
        <path d={`M862 ${y + 14} H908 M862 ${y + 26} H908 M862 ${y + 38} H908`} stroke="rgba(148,163,184,.2)" strokeWidth="1" />
        <text x="910" y={y + 72} textAnchor="middle" fontSize="10.5" fill={BOARD.grey}>
          {profile.name}
        </text>
        <rect x="812" y={y + 98} width="196" height="24" rx="12" fill="rgba(17,19,24,.92)" stroke="rgba(148,163,184,.3)" />
        <text x="910" y={y + 114} textAnchor="middle" fontSize="11" fill={BOARD.textMid}>
          {visual.caption}
        </text>
      </g>
    )
  }

  return (
    <g onClick={() => onSelect(profile.agentKey)} cursor="pointer" role="button" aria-label={profile.name}>
      <title>{`${profile.name} · ${visual.caption}`}</title>
      {selected && <Reticle y={y} color={accent} />}
      {visual.heat && (
        <g stroke={accent} strokeOpacity=".4" strokeWidth="1.4" fill="none" strokeLinecap="round">
          <path className="ahc-heat" d={`M850 ${y - 6} q4 -7 0 -14`} />
          <path className="ahc-heat2" d={`M880 ${y - 6} q-4 -8 0 -15`} />
          <path className="ahc-heat3" d={`M910 ${y - 6} q4 -7 0 -14`} />
        </g>
      )}
      <text x="880" y={y - 26} textAnchor="middle" fontSize="8" fill={BOARD.textFaint} letterSpacing="1" style={{ fontFamily: MONO }}>
        {visual.codeText}
      </text>
      <g fill={BOARD.pin}>
        {[836, 858, 880, 902].map((px) => (
          <rect key={`t${px}`} x={px} y={y - 4} width="9" height="4" />
        ))}
        {[836, 858, 880, 902].map((px) => (
          <rect key={`b${px}`} x={px} y={y + 84} width="9" height="4" />
        ))}
      </g>
      <rect x="820" y={y} width="120" height="84" rx="8" fill="#101820" stroke={accent} strokeOpacity=".85" strokeWidth="1.6" />
      <rect x="825" y={y + 5} width="110" height="74" rx="5" fill="none" stroke="rgba(255,255,255,.05)" />
      <rect
        x="858"
        y={y + 24}
        width="44"
        height="34"
        rx="5"
        fill={visual.dieBeat ? `url(#ahc-die-${index})` : 'none'}
        className={visual.dieBeat ?? undefined}
      />
      <rect x="858" y={y + 24} width="44" height="34" rx="5" fill="none" stroke={accent} strokeWidth="1.1" />
      {[832, 842, 852, 862].map((lx, i) => (
        <Led key={lx} x={lx} y={y + 10} color={ledColor} visual={visual} index={i} />
      ))}
      <text x="880" y={y + 75} textAnchor="middle" fontSize="10.5" fill={accent}>
        {profile.name}
      </text>
      <rect x="782" y={y + 106} width="196" height="24" rx="12" fill="rgba(17,19,24,.92)" stroke={accent} strokeOpacity=".55" />
      <text x="880" y={y + 122} textAnchor="middle" fontSize="11" fill={accent}>
        {visual.caption}
      </text>
    </g>
  )
}

export function AgentChips({
  items,
  selectedKey,
  onSelectAgent,
}: {
  items: AgentOverviewItem[]
  selectedKey: string | null
  onSelectAgent: (agentKey: string) => void
}) {
  return (
    <>
      {items.map((item, i) => (
        <AgentChip
          key={item.profile.agentKey}
          item={item}
          index={i}
          selected={item.profile.agentKey === selectedKey}
          onSelect={onSelectAgent}
        />
      ))}
    </>
  )
}
