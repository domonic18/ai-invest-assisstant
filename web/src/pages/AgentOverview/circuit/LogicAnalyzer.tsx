/**
 * 逻辑分析仪 LA-4CH：日内业务时间线（REV4）。波形 = 当日事件流（实线=已发生、
 * 虚线=计划窗预告），NOW 标记当前北京时刻，红标 = 委托事件，CH4 无载波 = 未启用。
 * 通道数据：CH1 引擎 = 全部 agent recentActivity 聚合；CH2-4 = 各 agent
 * （活动脉冲 + nextTasks 未来虚影）；09:25—18:35 线性时间轴。
 */
import dayjs from 'dayjs'

import type { AgentOverviewItem } from '@ai-invest/shared'

import { bjNow } from '@/utils/beijing'

import { BOARD, MONO } from './boardTheme'
import type { LatestOrder } from './Peripherals'
import { DAY_TICKS, beijingMinutes, groupPulses, minutesToX } from './timeAxis'

const CH_BASE_Y = [500, 556, 612, 668] as const
const WAVE_X0 = 150
const WAVE_X1 = 345

function pulsePath(x: number, baseY: number, height: number): string {
  return `M${x} ${baseY} v-${height} h3 v${height} h2 v-${height} h3 v${height}`
}

function ChannelWave({
  baseY,
  color,
  solidMinutes,
  futureMinutes,
  noCarrier,
  liveDot,
}: {
  baseY: number
  color: string
  solidMinutes: number[]
  futureMinutes: number[]
  noCarrier: boolean
  liveDot: boolean
}) {
  if (noCarrier) {
    return (
      <>
        <path d={`M${WAVE_X0} ${baseY + 8} h${WAVE_X1 - WAVE_X0}`} stroke="rgba(148,163,184,.3)" strokeWidth="1.4" strokeDasharray="4 4" />
        <text x={(WAVE_X0 + WAVE_X1) / 2} y={baseY + 4} textAnchor="middle" fontSize="8" fill="#3f4653" letterSpacing="2" style={{ fontFamily: MONO }}>
          NO CARRIER
        </text>
      </>
    )
  }
  const solids = groupPulses(solidMinutes)
  const futures = groupPulses(futureMinutes)
  return (
    <>
      <path d={`M${WAVE_X0} ${baseY} H${WAVE_X1}`} stroke={color} strokeOpacity=".15" strokeWidth="1" />
      {solids.map((g) => (
        <path
          key={`s${g.x}`}
          d={pulsePath(g.x, baseY, 8 + Math.min(g.count, 3) * 2)}
          fill="none"
          stroke={color}
          strokeOpacity=".85"
          strokeWidth="1.6"
        />
      ))}
      {futures.map((g) => (
        <path
          key={`f${g.x}`}
          d={pulsePath(g.x, baseY, 8 + Math.min(g.count, 3) * 2)}
          fill="none"
          stroke={color}
          strokeOpacity=".35"
          strokeWidth="1.4"
          strokeDasharray="3 2"
        />
      ))}
      {liveDot && <circle cx={WAVE_X0 + 5} cy={baseY} r="2.4" fill={BOARD.cyanPale} className="ahc-livedot" />}
    </>
  )
}

function activityMinutes(items: AgentOverviewItem[]): number[] {
  const today = bjNow().format('YYYY-MM-DD')
  return items
    .flatMap((item) => item.recentActivity)
    .filter((act) => act.occurredAt && dayjs(act.occurredAt).format('YYYY-MM-DD') === today)
    .map((act) => beijingMinutes(act.occurredAt!))
    .filter((m): m is number => m != null)
}

function planMinutes(item: AgentOverviewItem): number[] {
  const today = bjNow().format('YYYY-MM-DD')
  return item.nextTasks
    .filter((task) => dayjs(task.scheduledAt).format('YYYY-MM-DD') === today)
    .map((task) => beijingMinutes(task.scheduledAt))
    .filter((m): m is number => m != null)
}

export function LogicAnalyzer({
  items,
  latestOrder,
  nowMinutes,
  reducedMotion,
}: {
  items: AgentOverviewItem[]
  latestOrder: (LatestOrder & { agentKey: string }) | null
  /** 当前北京分钟数（注入便于测试）。 */
  nowMinutes: number
  reducedMotion: boolean
}) {
  const nowX = minutesToX(nowMinutes)
  const nowLabel = dayjs().startOf('day').add(nowMinutes, 'minute').format('HH:mm')
  const agents = items.slice(0, 3)
  const engineSolid = activityMinutes(items)
  const orderChannelIndex = latestOrder
    ? agents.findIndex((a) => a.profile.agentKey === latestOrder.agentKey)
    : -1
  const orderY = orderChannelIndex >= 0 ? CH_BASE_Y[orderChannelIndex + 1] : null
  const orderX = latestOrder ? minutesToX(latestOrder.minutes) : null

  return (
    <g>
      <rect x="60" y="420" width="310" height="315" rx="12" fill="#0d120f" stroke="rgba(52,211,153,.35)" strokeWidth="1.2" />
      <rect x="66" y="426" width="298" height="303" rx="8" fill="none" stroke="rgba(255,255,255,.04)" />
      <text x="78" y="446" fontSize="11" fill={BOARD.greenSoft} letterSpacing="1">
        逻辑分析仪 · 日内业务时间线
      </text>
      <text x="352" y="446" textAnchor="end" fontSize="8.5" fill={BOARD.textFaint} style={{ fontFamily: MONO }}>
        LA-4CH
      </text>
      <text x="78" y="461" fontSize="8" fill={BOARD.grey} style={{ fontFamily: MONO }}>
        实线=已发生 · 虚线=计划窗 · 红标=委托
      </text>
      <line x1="78" y1="470" x2="352" y2="470" stroke="rgba(52,211,153,.18)" />
      <path d="M370 480 H398 V452 H430" fill="none" stroke="rgba(148,163,184,.35)" strokeWidth="1.2" strokeDasharray="3 3" />
      <text x="376" y="472" fontSize="8" fill={BOARD.grey} style={{ fontFamily: MONO }}>
        PROBE×4
      </text>

      <g stroke="rgba(52,211,153,.10)">
        <line x1="78" y1="528" x2="352" y2="528" />
        <line x1="78" y1="584" x2="352" y2="584" />
        <line x1="78" y1="640" x2="352" y2="640" />
      </g>

      {/* CH1 引擎（聚合全部 agent 当日活动） */}
      <text x="78" y="494" fontSize="9" fill={BOARD.greenSoft} style={{ fontFamily: MONO }}>
        CH1 引擎
      </text>
      <ChannelWave baseY={CH_BASE_Y[0]} color={BOARD.green} solidMinutes={engineSolid} futureMinutes={[]} noCarrier={false} liveDot={false} />

      {/* CH2-4 Agent 通道 */}
      {agents.map((agent, i) => {
        const baseY = CH_BASE_Y[i + 1]
        const off = agent.runtimeState === 'off'
        const accent = agent.profile.accentColor ?? BOARD.cyan
        return (
          <g key={agent.profile.agentKey}>
            <text x="78" y={baseY - 6} fontSize="9" fill={off ? BOARD.grey : accent} style={{ fontFamily: MONO }}>
              CH{i + 2} {agent.profile.name}
            </text>
            <ChannelWave
              baseY={baseY}
              color={accent}
              solidMinutes={off ? [] : activityMinutes([agent])}
              futureMinutes={off ? [] : planMinutes(agent)}
              noCarrier={off}
              liveDot={!off && !reducedMotion && agent.runtimeState === 'working'}
            />
          </g>
        )
      })}
      {agents.length < 3 && (
        <>
          <text x="78" y={CH_BASE_Y[agents.length + 1] - 6} fontSize="9" fill={BOARD.grey} style={{ fontFamily: MONO }}>
            CH{agents.length + 2} —
          </text>
          <ChannelWave baseY={CH_BASE_Y[agents.length + 1]} color={BOARD.grey} solidMinutes={[]} futureMinutes={[]} noCarrier liveDot={false} />
        </>
      )}

      {/* 委托红标 */}
      {latestOrder && orderY != null && orderX != null && (
        <g>
          <circle cx={orderX} cy={orderY - 12} r="3" fill={BOARD.red} className="ahc-nowpulse" />
          <circle cx={orderX} cy={orderY - 12} r="6" fill="none" stroke="rgba(248,81,73,.5)" strokeWidth="1" className="ahc-nowpulse" />
          <text x={orderX + 5} y={orderY + 19} fontSize="7.5" fill={BOARD.redSoft} style={{ fontFamily: MONO }}>
            {latestOrder.ackTime} 委托
          </text>
        </g>
      )}

      {/* NOW 标记（历史拖尾 + 定驻线） */}
      <rect x={WAVE_X0} y="476" width={Math.max(nowX - WAVE_X0, 0)} height="210" fill="url(#ahc-histTrail)" />
      <rect x={nowX} y="476" width="1.6" height="210" fill={BOARD.cyanPale} className="ahc-nowpulse" />
      <rect x={nowX - 18} y="462" width="40" height="13" rx="3" fill="#0d2b28" stroke="rgba(165,243,252,.6)" />
      <text x={nowX + 2} y="472" textAnchor="middle" fontSize="8" fill={BOARD.cyanPale} style={{ fontFamily: MONO }}>
        NOW {nowLabel}
      </text>

      {/* 时间轴：刻度 = 业务日程（实=已过 / 虚=未来） */}
      <path d={`M${WAVE_X0} 690 H${WAVE_X1}`} stroke="rgba(148,163,184,.3)" strokeWidth="1" />
      <g fontSize="7.5" fill={BOARD.grey} style={{ fontFamily: MONO }}>
        {DAY_TICKS.map((tick) => {
          const x = minutesToX(tick.min)
          const passed = nowMinutes >= tick.min
          return (
            <g key={tick.label}>
              <path d={`M${x} 686 V694`} stroke={BOARD.grey} strokeDasharray={passed ? undefined : '2 2'} />
              <text x={x} y="705" textAnchor="middle">
                {tick.label}
              </text>
            </g>
          )
        })}
      </g>
      <text x="78" y="722" fontSize="8.5" fill={BOARD.textFaint} style={{ fontFamily: MONO }}>
        TRIG AUTO · 09:25—18:35 · 刻度=计划任务窗
      </text>
    </g>
  )
}
