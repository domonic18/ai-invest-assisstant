/**
 * 主板外设列：知识库存储阵列 / 资讯电报 / 情绪雷达 / 模拟柜台 I/O / Celery 消息总线
 * + 零散元件（C12/C27/R08/TP1 丝印）。心跳一律「文字+灯」双通道，数据来自
 * Celery 任务方框（领域关键词匹配）与系统状态探测，无数据如实显示「今日静默」。
 * Celery 总线内嵌任务方框条（与服务状态页 CeleryQueuesCard 同源数据、同状态语义：
 * 排队灰 / 执行中青闪 / 成功绿 / 部分成功与失败红黄 / 跳过淡灰描边），悬停 antd
 * Tooltip 展示与服务状态页相同的任务详情；RT/BA/HV 三队列恒驻，无任务队列画虚线
 * 空槽位让人一眼看出队列结构；只统计「今日」任务避免隔夜留痕冒充当日活跃。
 */
import dayjs from 'dayjs'

import { Tooltip } from 'antd'

import type { CeleryQueues, CeleryTaskSquare, CeleryTaskState, SystemStatus } from '@ai-invest/shared'

import { CeleryTaskTooltipContent } from '@/components/CeleryTaskTooltip'
import { toBeijing } from '@/utils/beijing'

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

/** 任务方框配色（服务状态页语义的 PCB 色板映射）；dim=淡色填充+同色描边，暗底上仍可辨形。 */
const TASK_SQUARE_STYLE: Record<CeleryTaskState, { fill: string; dim?: boolean }> = {
  pending: { fill: BOARD.socketGrey },
  running: { fill: BOARD.cyan },
  success: { fill: BOARD.greenLed },
  partial: { fill: BOARD.amber },
  failed: { fill: BOARD.red },
  skipped: { fill: BOARD.grey, dim: true },
}

const QUEUE_TAG: Record<string, string> = {
  'collector.realtime': 'RT',
  'collector.batch': 'BA',
  'collector.heavy': 'HV',
}

/** 主板固定展示的 Celery 队列集合（collector 三队列，label 与服务状态页 QUEUE_LABELS 对齐，
 * 数据未达时用此回退，保证空槽位提示仍是中文队列名）。 */
const CANONICAL_QUEUES = [
  { name: 'collector.realtime', label: '实时队列' },
  { name: 'collector.batch', label: '批量队列' },
  { name: 'collector.heavy', label: '重载队列' },
]

/** 主板任务方框条每队列最多展示数（tasks 前排 running、后排最新终态，取前缀即可）。 */
const SQUARES_PER_QUEUE = 5

/** 任务方框条 + 汇总行：三条队列恒驻展示（与服务状态页 QUEUE_LABELS 同源语义），
 * 无任务的队列画虚线空槽位而非消失；方块只看今日任务（finishedAt 优先、回落
 * startedAt 的北京日期），汇总按全量今日任务统计，跳过数单独列出让灰方块可自解释。 */
function TaskSquares({ queues, today }: { queues: CeleryQueues | undefined; today: string }) {
  const isToday = (task: CeleryTaskSquare) => {
    const stamp = task.finishedAt ?? task.startedAt
    return stamp != null && toBeijing(dayjs(stamp)).format('YYYY-MM-DD') === today
  }
  const byName = new Map((queues?.queues ?? []).map((queue) => [queue.name, queue]))
  const groups = CANONICAL_QUEUES.map(({ name, label }) => {
    const queue = byName.get(name) ?? { name, label, pendingTotal: 0, tasks: [] }
    return { queue, shown: queue.tasks.filter(isToday).slice(0, SQUARES_PER_QUEUE) }
  })
  const counts = { running: 0, abnormal: 0, success: 0, skipped: 0 }
  for (const queue of queues?.queues ?? []) {
    for (const task of queue.tasks) {
      if (!isToday(task)) continue
      if (task.state === 'running') counts.running += 1
      else if (task.state === 'failed' || task.state === 'partial') counts.abnormal += 1
      else if (task.state === 'success') counts.success += 1
      else if (task.state === 'skipped') counts.skipped += 1
    }
  }

  let cursor = 392
  return (
    <g>
      {groups.map(({ queue, shown }, gi) => {
        const start = cursor
        cursor += 17
        const tag = QUEUE_TAG[queue.name] ?? queue.name.slice(0, 2).toUpperCase()
        const squares = shown.map((task) => {
          const style = TASK_SQUARE_STYLE[task.state]
          const rect = (
            <Tooltip key={task.key} title={<CeleryTaskTooltipContent task={task} />}>
              <rect
                x={cursor}
                y={680}
                width="9"
                height="9"
                rx="2"
                fill={style.fill}
                fillOpacity={style.dim ? 0.4 : 1}
                stroke={style.fill}
                strokeOpacity={style.dim ? 0.7 : 0.85}
                strokeWidth="1"
                className={task.state === 'running' ? 'ahc-corebeat' : undefined}
              />
            </Tooltip>
          )
          cursor += 12
          return rect
        })
        const emptySlot =
          shown.length === 0 ? (
            <Tooltip key="empty" title={`「${queue.label}」今日无任务留痕`}>
              <rect
                x={cursor}
                y={680}
                width="9"
                height="9"
                rx="2"
                fill="none"
                stroke={BOARD.lineSoft}
                strokeWidth="1"
                strokeDasharray="2 2"
                pointerEvents="all"
              />
            </Tooltip>
          ) : null
        if (shown.length === 0) cursor += 12
        cursor += 8
        return (
          <g key={queue.name}>
            {gi > 0 && (
              <line x1={start - 6} y1={679} x2={start - 6} y2={690} stroke={BOARD.lineSoft} strokeWidth="1" />
            )}
            <text x={start} y={687.5} fontSize="6.5" fill={BOARD.textDim} style={{ fontFamily: MONO }}>
              {tag}
            </text>
            {squares}
            {emptySlot}
          </g>
        )
      })}
      <text x="392" y="707" fontSize="8" fill={BOARD.textMid} style={{ fontFamily: MONO }}>
        {counts.running + counts.abnormal + counts.success + counts.skipped === 0
          ? '今日暂无任务留痕'
          : <>
              {'执行中 '}
              <tspan fill={BOARD.cyan}>{counts.running}</tspan>
              {' · 异常 '}
              <tspan fill={counts.abnormal > 0 ? BOARD.red : BOARD.textMid}>{counts.abnormal}</tspan>
              {' · 正常 '}
              <tspan fill={BOARD.greenLed}>{counts.success}</tspan>
              {counts.skipped > 0 && (
                <>
                  {' · 跳过 '}
                  <tspan>{counts.skipped}</tspan>
                </>
              )}
            </>}
      </text>
    </g>
  )
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

      {/* Celery 消息总线 + 任务方框条 */}
      <g>
        <text x="520" y="632" textAnchor="middle" fontSize="11" fill={BOARD.amberSoft}>
          Celery 消息总线
        </text>
        <rect x="380" y="640" width="280" height="76" rx="10" fill="#161410" stroke="rgba(210,153,34,.5)" strokeWidth="1.4" />
        <path d="M396 656 H644 M396 668 H644" stroke="rgba(210,153,34,.35)" strokeWidth="1.4" />
        {!reducedMotion && (
          <>
            <rect width="14" height="8" rx="2" fill={BOARD.amber}>
              <animateMotion dur="3s" repeatCount="indefinite" path="M396 652 H630" />
            </rect>
            <rect width="14" height="8" rx="2" fill="rgba(210,153,34,.55)">
              <animateMotion dur="3s" begin="1.4s" repeatCount="indefinite" path="M644 664 H410" />
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
        <TaskSquares queues={celeryQueues} today={today} />
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
