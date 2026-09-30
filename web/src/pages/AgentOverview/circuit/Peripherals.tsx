/**
 * 主板外设列：知识库存储阵列 / 资讯电报 / 情绪雷达 / 模拟柜台 I/O / Celery 消息总线
 * + 零散元件（C12/C27/R08/TP1 丝印）。心跳一律「文字+灯」双通道，数据来自
 * Celery 任务方框（领域关键词匹配）与系统状态探测，无数据如实显示「今日静默」。
 */
import type { CeleryQueues, SystemStatus } from '@ai-invest/shared'

import { BOARD, MONO } from './boardTheme'
import { counterHeartbeat, domainHeartbeat } from './heartbeats'

/** 最新一笔委托（右栏观测数据里最新的 execute 行，用于柜台 ORD/ACK 与 LA 红标）。 */
export interface LatestOrder {
  volume: number | null
  price: number | null
  /** HH:mm:ss 本地渲染串（柜台 ACK 丝印）。 */
  ackTime: string
  /** 委托发生时刻的北京分钟数（LA 红标定位，由页面层 timeAxis.beijingMinutes 算出）。 */
  minutes: number
}

function HeartbeatLed({ x, y, up }: { x: number; y: number; up: boolean | null }) {
  const color = up == null ? BOARD.grey : up ? BOARD.greenLed : BOARD.red
  return <circle cx={x} cy={y} r="2.4" fill={color} className="ahc-corebeat" />
}

export function Peripherals({
  systemStatus,
  celeryQueues,
  latestOrder,
  today,
  reducedMotion,
}: {
  systemStatus: SystemStatus | undefined
  celeryQueues: CeleryQueues | undefined
  latestOrder: LatestOrder | null
  today: string
  reducedMotion: boolean
}) {
  const tasks = (celeryQueues?.queues ?? []).flatMap((q) => q.tasks)
  const kbBeat = domainHeartbeat(tasks, ['kb', 'extract', '知识'], today)
  const newsBeat = domainHeartbeat(tasks, ['news', '电报', '资讯'], today)
  const sentBeat = domainHeartbeat(tasks, ['sentiment', '抖音', '情绪'], today)
  const counter = counterHeartbeat(
    systemStatus?.items.find((item) => item.key === 'counter'),
  )
  const celeryItem = systemStatus?.items.find((item) => item.key === 'celery')
  const celeryUp = celeryItem ? celeryItem.status === 'up' : null
  const queues = (celeryQueues?.queues ?? []).slice(0, 2)
  const backlog = (celeryQueues?.queues ?? []).reduce((sum, q) => sum + q.pendingTotal, 0)

  return (
    <>
      {/* 知识库 · 存储阵列 */}
      <g>
        <text x="115" y="108" textAnchor="middle" fontSize="11" fill={BOARD.purpleText}>
          知识库 · 存储阵列
        </text>
        <rect x="60" y="116" width="110" height="94" rx="10" fill="#10141f" stroke="rgba(168,85,247,.5)" strokeWidth="1.4" />
        {[130, 149, 168, 187].map((by, i) => (
          <g key={by}>
            <rect x="74" y={by} width="82" height="13" rx="3" fill="none" stroke={`rgba(168,85,247,${0.55 - i * 0.08})`} />
            <circle cx="146" cy={by + 6.5} r="2.4" fill={BOARD.purple} className={`ahc-led${(i % 3) + 1}`} />
          </g>
        ))}
        <HeartbeatLed x={70} y={220} up={kbBeat !== '今日静默'} />
        <text x="78" y="223.5" fontSize="8" fill={BOARD.textMid} style={{ fontFamily: MONO }}>
          {kbBeat}
        </text>
      </g>

      {/* 资讯电报 */}
      <g>
        <rect x="60" y="248" width="110" height="40" rx="9" fill="#101820" stroke="rgba(88,166,255,.5)" />
        <circle cx="76" cy="268" r="2.6" fill={BOARD.red} className="ahc-corebeat" />
        <text x="88" y="272" fontSize="10.5" fill={BOARD.blueSoft}>
          资讯电报
        </text>
        <path d="M150 262 v-8 M145 257 a7 7 0 0 1 10 0" stroke={BOARD.blue} strokeWidth="1.4" fill="none" />
        <text x="60" y="302" fontSize="8" fill={BOARD.textMid} style={{ fontFamily: MONO }}>
          {newsBeat}
        </text>
      </g>

      {/* 情绪雷达 */}
      <g>
        <rect x="60" y="316" width="110" height="40" rx="9" fill="#1a1018" stroke="rgba(244,114,182,.5)" />
        <text x="74" y="336" fontSize="10.5" fill={BOARD.pinkSoft}>
          情绪雷达
        </text>
        <text x="60" y="370" fontSize="8" fill={BOARD.textMid} style={{ fontFamily: MONO }}>
          {sentBeat}
        </text>
      </g>

      {/* 模拟柜台 · I/O */}
      <g>
        <text x="1060" y="322" textAnchor="middle" fontSize="11" fill={BOARD.greenText}>
          模拟柜台 · I/O
        </text>
        <rect x="1010" y="330" width="100" height="92" rx="10" fill="#101814" stroke="rgba(46,160,67,.55)" strokeWidth="1.4" />
        <HeartbeatLed x={1022} y={344} up={counter.up} />
        <rect x="1024" y="356" width="72" height="10" rx="3" fill="none" stroke="rgba(46,160,67,.5)" />
        <rect x="1024" y="372" width="72" height="10" rx="3" fill="none" stroke="rgba(46,160,67,.5)" />
        <rect x="1024" y="372" width="46" height="10" rx="3" fill="rgba(46,160,67,.35)" />
        <text x="1024" y="400" fontSize="9.5" fill={BOARD.greenText} style={{ fontFamily: MONO }}>
          {latestOrder?.volume != null && latestOrder.price != null
            ? `ORD ${latestOrder.volume}×${latestOrder.price}`
            : 'ORD 今日无委托'}
        </text>
        <text x="1024" y="413" fontSize="9.5" fill={BOARD.grey} style={{ fontFamily: MONO }}>
          {counter.text}
          {latestOrder ? ` · ACK ${latestOrder.ackTime}` : ''}
        </text>
      </g>

      {/* Celery 消息总线 */}
      <g>
        <text x="520" y="632" textAnchor="middle" fontSize="11" fill={BOARD.amberSoft}>
          Celery 消息总线
        </text>
        <rect x="380" y="640" width="280" height="60" rx="10" fill="#161410" stroke="rgba(210,153,34,.5)" strokeWidth="1.4" />
        <path d="M396 660 H644 M396 674 H644" stroke="rgba(210,153,34,.35)" strokeWidth="1.4" />
        {!reducedMotion && (
          <>
            <rect width="14" height="8" rx="2" fill={BOARD.amber}>
              <animateMotion dur="3s" repeatCount="indefinite" path="M396 656 H630" />
            </rect>
            <rect width="14" height="8" rx="2" fill="rgba(210,153,34,.55)">
              <animateMotion dur="3s" begin="1.4s" repeatCount="indefinite" path="M644 670 H410" />
            </rect>
          </>
        )}
        <HeartbeatLed x={660} y={654} up={celeryUp} />
        <text x="668" y="657.5" fontSize="8" fill={BOARD.textMid} style={{ fontFamily: MONO }}>
          {queues[0] ? `${queues[0].label}@` : 'worker@'}
        </text>
        <HeartbeatLed x={660} y={672} up={celeryUp} />
        <text x="668" y="675.5" fontSize="8" fill={BOARD.textMid} style={{ fontFamily: MONO }}>
          {queues[1] ? `${queues[1].label}@` : 'heavy@'}
        </text>
        <text x="668" y="693" fontSize="8" fill={BOARD.amber} style={{ fontFamily: MONO }}>
          积压 ×{backlog}
        </text>
      </g>

      {/* 零散元件 */}
      <g>
        <circle cx="395" cy="300" r="7" fill="#0e1512" stroke="rgba(52,211,153,.4)" strokeWidth="1.2" />
        <text x="395" y="291" textAnchor="middle" fontSize="7.5" fill={BOARD.textFaint} style={{ fontFamily: MONO }}>
          C12
        </text>
        <circle cx="700" cy="600" r="7" fill="#0e1512" stroke="rgba(52,211,153,.4)" strokeWidth="1.2" />
        <text x="700" y="591" textAnchor="middle" fontSize="7.5" fill={BOARD.textFaint} style={{ fontFamily: MONO }}>
          C27
        </text>
        <rect x="1000" y="466" width="22" height="10" rx="2" fill="#0e1512" stroke="rgba(210,153,34,.45)" />
        <path d="M1003 471 l3 -3 3 6 3 -6 3 6 3 -6 3 3" stroke="rgba(210,153,34,.6)" strokeWidth="1" fill="none" />
        <text x="1011" y="462" textAnchor="middle" fontSize="7.5" fill="#4a4436" style={{ fontFamily: MONO }}>
          R08
        </text>
        <circle cx="90" cy="70" r="4" fill="none" stroke="rgba(148,163,184,.4)" />
        <text x="100" y="74" fontSize="7.5" fill="#3f4653" style={{ fontFamily: MONO }}>
          TP1
        </text>
      </g>
    </>
  )
}
