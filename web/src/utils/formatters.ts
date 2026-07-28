import cronstrue from 'cronstrue'
import 'cronstrue/locales/zh_CN'

import { semanticColors } from '@/theme/colors'
import { useSettingsStore } from '@/stores/settings'

export function formatNumber(value: number, decimals = 2): string {
  return value.toFixed(decimals)
}

/** 将 Cron 表达式转换为中文自然语言描述；解析失败时原样返回。 */
export function formatCronExpression(value: string | null | undefined): string {
  if (!value) return '-'
  try {
    return cronstrue.toString(value, { locale: 'zh_CN' })
  } catch {
    return value
  }
}

export function formatPercent(value: number, decimals = 2): string {
  return `${value > 0 ? '+' : ''}${value.toFixed(decimals)}%`
}

export function formatAmount(value: number | null | undefined): string {
  if (value === null || value === undefined) return '-'
  const abs = Math.abs(value)
  const sign = value < 0 ? '-' : ''
  if (abs >= 1e12) return `${sign}${(abs / 1e12).toFixed(2)}万亿`
  if (abs >= 1e8) return `${sign}${(abs / 1e8).toFixed(1)}亿`
  if (abs >= 1e4) return `${sign}${(abs / 1e4).toFixed(1)}万`
  return `${sign}${abs.toFixed(0)}`
}

/** 封板时间："092500" → "09:25:00"（东财 6 位零填充格式）。 */
export function formatSealTime(value: string | null | undefined): string {
  if (!value) return '-'
  const digits = value.padStart(6, '0')
  return `${digits.slice(0, 2)}:${digits.slice(2, 4)}:${digits.slice(4, 6)}`
}

const RISE_COLOR = { cn: 'text-red-500', us: 'text-green-500' } as const
const FALL_COLOR = { cn: 'text-green-500', us: 'text-red-500' } as const
const RISE_COLOR_SOFT = { cn: 'text-red-400', us: 'text-green-400' } as const
const FALL_COLOR_SOFT = { cn: 'text-green-400', us: 'text-red-400' } as const
const RISE_HEX = semanticColors.rise
const FALL_HEX = semanticColors.fall

const scheme = () => useSettingsStore.getState().colorScheme

export function riseColor(): string {
  return RISE_COLOR[scheme()]
}

export function fallColor(): string {
  return FALL_COLOR[scheme()]
}

export function riseColorSoft(): string {
  return RISE_COLOR_SOFT[scheme()]
}

export function fallColorSoft(): string {
  return FALL_COLOR_SOFT[scheme()]
}

export function riseHex(): string {
  return RISE_HEX[scheme()]
}

export function fallHex(): string {
  return FALL_HEX[scheme()]
}

export function changeColor(value: number | null | undefined): string {
  if (value === null || value === undefined) return 'text-gray-400'
  return value >= 0 ? riseColor() : fallColor()
}

export function changeHex(value: number | null | undefined): string {
  if (value === null || value === undefined) return '#8c8c8c'
  return value >= 0 ? riseHex() : fallHex()
}
