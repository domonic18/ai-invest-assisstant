import type { MovingAverageConfig } from '@ai-invest/shared'

export const MAX_MA_COUNT = 6

export const PRESET_COLORS = [
  '#f0b429',
  '#9d7ff5',
  '#3fb6e0',
  '#e8833a',
  '#c0c4d0',
  '#22c55e',
  '#ef4444',
  '#06b6d4',
]

export function sortByPeriod(configs: MovingAverageConfig[]): MovingAverageConfig[] {
  return [...configs].sort((a, b) => a.period - b.period)
}

export function nextDefaultPeriod(configs: MovingAverageConfig[]): number {
  if (configs.length === 0) return 5
  const maxPeriod = Math.max(...configs.map((c) => c.period))
  const next = Math.ceil((maxPeriod + 10) / 10) * 10
  return Math.min(next, 500)
}

export function nextDefaultColor(configs: MovingAverageConfig[]): string {
  const used = new Set(configs.map((c) => c.color.toLowerCase()))
  return PRESET_COLORS.find((color) => !used.has(color.toLowerCase())) ?? '#8884d8'
}
