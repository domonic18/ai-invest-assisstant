/**
 * 电路脉冲主板视觉主题（REV4 设计稿定稿色板）：PCB 底色 / 信号色 / 卡片色。
 * 身份色 = Agent accentColor（由 chip 渲染处内联传入），此处只放平台固定色。
 * 所有 keyframes/utility class 以 ahc- 前缀注入，避免污染全局。
 */

export const BOARD = {
  bg: '#0a0f0d',
  pcbEdge: 'rgba(52,211,153,.22)',
  pcbEdgeSoft: 'rgba(52,211,153,.08)',
  pin: '#26312c',
  card: '#181a21',
  cardDeep: '#111318',
  line: '#23262d',
  lineSoft: '#2e323c',
  text: '#f0f1f5',
  textMid: '#8a8f98',
  textDim: '#5c616e',
  textFaint: '#3f5a4e',
  green: '#34d399',
  greenLed: '#2ea043',
  greenSoft: '#6ee7b7',
  greenText: '#7ee2a8',
  greenPale: '#a7f3d0',
  cyan: '#22d3ee',
  cyanSoft: '#67e8f9',
  cyanPale: '#a5f3fc',
  purple: '#a855f7',
  purpleSoft: '#c084fc',
  purplePale: '#e9d5ff',
  purpleText: '#d8b4fe',
  blue: '#58a6ff',
  blueSoft: '#93c5fd',
  pink: '#f472b6',
  pinkSoft: '#f9a8d4',
  red: '#f85149',
  redSoft: '#f87171',
  redPale: '#fca5a5',
  amber: '#d29922',
  amberSoft: '#e7c26a',
  amberPaused: '#f59e0b',
  grey: '#5c616e',
  greySoft: '#8a8f98',
  socketGrey: '#475060',
  silk: '#2b3a33',
} as const

const KF = [
  '@keyframes ahc-blink { 50% { opacity:.35 } }',
  '@keyframes ahc-tp { 0%,100%{opacity:.3} 50%{opacity:1} }',
  '@keyframes ahc-feedin { from{opacity:0; transform:translateY(-8px)} to{opacity:1; transform:none} }',
  '@keyframes ahc-dashflow { to { stroke-dashoffset:-48 } }',
  '@keyframes ahc-corebeat { 0%,100%{opacity:1} 50%{opacity:.3} }',
  '@keyframes ahc-ledchase { 0%,100%{opacity:1} 33%{opacity:.2} 66%{opacity:.5} }',
  '@keyframes ahc-heatrise { 0%{opacity:0; transform:translateY(2px)} 40%{opacity:.8} 100%{opacity:0; transform:translateY(-4px)} }',
  '@keyframes ahc-nowpulse { 0%,100%{opacity:.95} 50%{opacity:.4} }',
  '@keyframes ahc-livesweep { from{transform:translateX(0)} to{transform:translateX(89px)} }',
].join('\n')

const CLS = [
  '.ahc-mono { font-family:"SF Mono","Fira Code",ui-monospace,Menlo,monospace; }',
  '.ahc-trace-fast { stroke-dasharray:10 6; animation:ahc-dashflow 1s linear infinite; }',
  '.ahc-trace-slow { stroke-dasharray:5 9; animation:ahc-dashflow 3.2s linear infinite; }',
  '.ahc-trace-clk { stroke-dasharray:2 6; animation:ahc-dashflow 2.4s linear infinite; }',
  '.ahc-corebeat { animation:ahc-corebeat 1.6s ease-in-out infinite; }',
  '.ahc-corebeat-slow { animation:ahc-corebeat 4s ease-in-out infinite; }',
  '.ahc-led1 { animation:ahc-ledchase 1.8s linear infinite; }',
  '.ahc-led2 { animation:ahc-ledchase 1.8s linear infinite .45s; }',
  '.ahc-led3 { animation:ahc-ledchase 1.8s linear infinite .9s; }',
  '.ahc-led4 { animation:ahc-ledchase 1.8s linear infinite 1.35s; }',
  '.ahc-heat { animation:ahc-heatrise 1.8s ease-in-out infinite; }',
  '.ahc-heat2 { animation:ahc-heatrise 1.8s ease-in-out infinite .5s; }',
  '.ahc-heat3 { animation:ahc-heatrise 1.8s ease-in-out infinite 1s; }',
  '.ahc-nowpulse { animation:ahc-nowpulse 2s ease-in-out infinite; }',
  '.ahc-livedot { animation:ahc-livesweep 3s linear infinite; }',
  '.ahc-feed-card { animation:ahc-feedin .5s ease both; }',
  '.ahc-typing i { animation:ahc-tp 1.2s ease-in-out infinite; }',
  '.ahc-typing i:nth-child(2) { animation-delay:.15s; }',
  '.ahc-typing i:nth-child(3) { animation-delay:.3s; }',
  '.ahc-reduced *, .ahc-reduced *::before, .ahc-reduced *::after { animation: none !important; }',
].join('\n')

/** 一次性注入主板 + 决策流动效（scoped class，无全局污染）。 */
export const BOARD_CSS = `${KF}\n${CLS}`

/** SVG 通用 mono 字体族（丝印 / 代码 / 附注）。 */
export const MONO = "'SF Mono','Fira Code',ui-monospace,Menlo,monospace"

/** 芯片插槽 Y 坐标（设计稿定稿：右列四槽位等距 150，额外 agent 顺延）。 */
export const CHIP_SLOT_Y = [186, 336, 486, 636] as const

export function chipSlotY(index: number): number {
  return index < CHIP_SLOT_Y.length ? CHIP_SLOT_Y[index] : CHIP_SLOT_Y[0] + index * 150
}
