/** 多空立场徽标：红涨绿跌配色走 scheme-aware helper，切换 colorScheme 自动翻转。 */

import type { ApiSocialStance } from '@ai-invest/shared'

import { useColorScheme } from '@/stores/settings'
import { fallHex, riseHex } from '@/utils/formatters'

import { STANCE_TEXT } from './labels'

interface StanceBadgeProps {
  stance: ApiSocialStance
  /** 判断置信度 0-1（tooltip 展示） */
  confidence?: number | null
}

export function StanceBadge({ stance, confidence }: StanceBadgeProps) {
  useColorScheme()
  const hex =
    stance === 'neutral' ? '#8c8c8c' : stance === 'bullish' ? riseHex() : fallHex()
  return (
    <span
      className="inline-flex shrink-0 items-center rounded px-1.5 py-0.5 text-xs font-medium leading-none"
      style={{
        color: hex,
        background: `${hex}1f`,
        border: `1px solid ${hex}55`,
      }}
      title={
        confidence !== null && confidence !== undefined
          ? `置信度 ${(confidence * 100).toFixed(0)}%`
          : undefined
      }
    >
      {STANCE_TEXT[stance]}
    </span>
  )
}
