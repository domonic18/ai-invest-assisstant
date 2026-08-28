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
