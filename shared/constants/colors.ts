/**
 * 设计 token：单一真相源（前后端统一常量层）。
 *
 * 涨跌色（红涨绿跌 / 绿涨红跌）的 scheme-aware 取色在 web 端
 * 仍走 `utils/formatters.ts` 的 `riseHex()/fallHex()`；本文件只持有静态色板。
 */

export const semanticColors = {
  rise: { cn: '#f85149', us: '#2ea043' },
  fall: { cn: '#2ea043', us: '#f85149' },
} as const

export const panelColors = {
  bg: '#0c0e12',
  border: '#23262e',
  textMuted: '#8c8c8c',
} as const

export type PanelColorKey = keyof typeof panelColors

/** Chart / graph color constants. */
export const ChartColors = {
  background: 'transparent',
  panelBg: panelColors.bg,
  panelBorder: panelColors.border,
  textMain: '#d1d4dc',
  textMuted: panelColors.textMuted,
  grid: '#1f2229',
  rise: '#ef4444',
  fall: '#22c55e',
} as const

/** 通用执行状态的 AntD Tag 颜色与中文标签（权威映射，全站唯一来源）。 */
export interface StatusTagMeta {
  color: string
  label: string
}

export const STATUS_TAG_META: Record<string, StatusTagMeta> = {
  success: { color: 'green', label: '成功' },
  failed: { color: 'red', label: '失败' },
  running: { color: 'processing', label: '运行中' },
  pending: { color: 'gold', label: '排队中' },
  partial: { color: 'orange', label: '部分成功' },
  skipped: { color: 'default', label: '跳过' },
  idle: { color: 'default', label: '空闲' },
}

export function statusTagColor(status: string): string {
  return STATUS_TAG_META[status]?.color ?? 'default'
}

export function statusLabel(status: string): string {
  return STATUS_TAG_META[status]?.label ?? status
}
