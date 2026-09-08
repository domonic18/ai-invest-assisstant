import { Tag } from 'antd'
import type { ReactNode } from 'react'

import { useColorScheme } from '@/stores/settings'
import { changeColor, changeHex } from '@/utils/formatters'

interface SparklineProps {
  points: number[]
  color: string
}

/** 迷你趋势线（原型 macro-card sparkline：120x30 svg polyline）。 */
function Sparkline({ points, color }: SparklineProps) {
  if (points.length < 2) return <div className="h-[30px] mt-0.5" />
  const min = Math.min(...points)
  const max = Math.max(...points)
  const span = max - min || 1
  const coords = points.map((p, i) => {
    const x = (i / (points.length - 1)) * 120
    const y = 28 - ((p - min) / span) * 26
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })
  return (
    <svg
      viewBox="0 0 120 30"
      preserveAspectRatio="none"
      className="block w-full h-[30px] mt-0.5"
    >
      <polyline
        points={coords.join(' ')}
        fill="none"
        stroke={color}
        strokeWidth={1.6}
      />
    </svg>
  )
}

interface MacroCardProps {
  name: string
  tag: string
  tagColor: string
  /** 主值（已格式化：指数千分位 / 债券 x.xxx% / 利差 +xx.xbp）。 */
  value: string
  /** 涨跌幅（百分点），正负决定配色；展示文案由 changeLabel 覆盖。 */
  changePct: number | null
  changeLabel?: string
  trend?: number[]
  footer?: ReactNode
  active?: boolean
  onClick?: () => void
}

export function MacroCard({
  name,
  tag,
  tagColor,
  value,
  changePct,
  changeLabel,
  trend,
  footer,
  active = false,
  onClick,
}: MacroCardProps) {
  useColorScheme()
  const chg =
    changePct === null
      ? '-'
      : (changeLabel ?? (changePct > 0 ? '+' : '') + changePct.toFixed(2) + '%')
  const sparkColor = changeHex(changePct)
  return (
    <div
      onClick={onClick}
      className={`min-h-[118px] flex flex-col gap-1 rounded-xl border p-3.5 px-4 transition-all cursor-pointer ${
        active
          ? 'border-[#5e6ad2]'
          : 'border-gray-800 hover:border-gray-600 hover:-translate-y-px'
      }`}
    >
      <div className="flex items-center gap-1.5">
        <span className="text-[13px] font-medium text-gray-400">{name}</span>
        <Tag color={tagColor} className="!mr-0 !text-[11px] !leading-4 !px-2">
          {tag}
        </Tag>
      </div>
      <div className="flex items-baseline gap-2">
        <span className="text-xl font-bold tracking-tight tabular-nums">
          {value}
        </span>
        <span
          className={`text-[11px] font-medium font-mono ${changeColor(changePct)}`}
        >
          {chg}
        </span>
      </div>
      {trend ? <Sparkline points={trend} color={sparkColor} /> : <div className="h-[30px] mt-0.5" />}
      {footer && (
        <div className="flex items-center justify-between text-[10px] text-gray-600">
          {footer}
        </div>
      )}
    </div>
  )
}

interface GhostCardProps {
  title: string
  note: string
}

/** 扩展位虚线卡（原型 ghost-card：未接入指标占位）。 */
export function GhostCard({ title, note }: GhostCardProps) {
  return (
    <div className="min-h-[118px] flex items-center justify-center rounded-xl border border-dashed border-gray-700 text-gray-600">
      <div className="text-center">
        <div className="text-lg mb-1">＋</div>
        <div className="text-[11px]">{title}</div>
        <div className="text-[10px] mt-0.5">{note}</div>
      </div>
    </div>
  )
}
