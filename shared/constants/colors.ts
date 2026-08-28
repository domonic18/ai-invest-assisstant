import { panelColors } from '../../web/src/theme/colors'

/** Re-export theme colors so backend/shared code can reference the same palette. */
export { panelColors }

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
