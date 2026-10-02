/**
 * Agent 运行态 → 芯片五态视觉推导（纯函数，可测）。
 * REV4 图例五态：工作（满载呼吸跑马）/ 已产出（晨峰后回落）/ 待机（慢心跳）
 * / 暂停（时钟门控）/ 未启用（空插槽）。身份色 = accentColor，状态一律由
 * LED 编排 + 呼吸节奏 + 文字标签表达，不依赖颜色（色盲可读）。
 */
import type { AgentOverviewItem } from '@ai-invest/shared'

import { BOARD } from './boardTheme'

export type ChipMode = 'run' | 'produced' | 'idle' | 'paused' | 'off'

export interface ChipVisual {
  mode: ChipMode
  /** 芯片顶部丝印代码行（AGT-XXX · RUN · …）。 */
  codeText: string
  /** 芯片下方胶囊文案：后端 state_label 优先，前端不虚报。 */
  caption: string
  /** 呼吸节奏 class；null = die 不上电。 */
  dieBeat: string | null
  /** LED 编排：chase=四灯跑马 / solid=单灯常亮 / slow=单灯慢闪 / none=全灭。 */
  led: 'chase' | 'solid' | 'slow' | 'none'
  /** 散热气流（满载）。 */
  heat: boolean
  /** 暂停态 LED 用琥珀色（其余用 accentColor）。 */
  ledColorOverride: string | null
}

const MODE_CAPTION: Record<ChipMode, string> = {
  run: '工作中',
  produced: '今日已产出',
  idle: '待机 · 慢心跳',
  paused: '已暂停 · 时钟门控',
  off: '未启用 · 插槽未上电',
}

const STATE_MODE: Record<AgentOverviewItem['runtimeState'], ChipMode> = {
  working: 'run',
  produced_today: 'produced',
  idle: 'idle',
  paused: 'paused',
  off: 'off',
}

export function deriveChipVisual(item: AgentOverviewItem): ChipVisual {
  const { runtimeState, profile, planCount, selectionCount, stateLabel } = item
  const mode = STATE_MODE[runtimeState]
  const code = `AGT-${profile.agentKey}`.toUpperCase()
  const caption = stateLabel ?? MODE_CAPTION[mode]
  switch (mode) {
    case 'run':
      return {
        mode: 'run',
        codeText: `${code} · RUN · 100% LOAD`,
        caption,
        dieBeat: 'ahc-corebeat',
        led: 'chase',
        heat: true,
        ledColorOverride: null,
      }
    case 'produced':
      return {
        mode: 'produced',
        codeText: `${code} · PRODUCED ×${planCount + selectionCount} · LOW`,
        caption,
        dieBeat: 'ahc-corebeat-slow',
        led: 'solid',
        heat: false,
        ledColorOverride: null,
      }
    case 'paused':
      return {
        mode: 'paused',
        codeText: `${code} · CLK GATED`,
        caption,
        dieBeat: null,
        led: 'slow',
        heat: false,
        ledColorOverride: BOARD.amberPaused,
      }
    case 'off':
      return {
        mode: 'off',
        codeText: 'SOCKET EMPTY · NO POWER',
        caption,
        dieBeat: null,
        led: 'none',
        heat: false,
        ledColorOverride: null,
      }
    case 'idle':
    default:
      return {
        mode: 'idle',
        codeText: `${code} · IDLE · 4s HB`,
        caption,
        dieBeat: 'ahc-corebeat-slow',
        led: 'slow',
        heat: false,
        ledColorOverride: null,
      }
  }
}
