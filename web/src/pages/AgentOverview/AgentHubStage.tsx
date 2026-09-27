/**
 * Agent Hub 分层舞台（D33）：三层自上而下——Agent 运行层 / 资源系统层
 * （五站同维度同款） / 基建层（状态灯五盒 + Celery 队列分组任务方框，
 * hover 看任务内容）。三层渲染共用 layoutLayers 像素坐标与容器实测尺寸：
 * ① HubBackgroundCanvas（网格 + 扫描线，页面唯一 rAF）；② SVG 连线层
 * （真实数据流边，fast 档 dash 流动 + animateMotion 光点，
 * prefers-reduced-motion 停用）；③ HTML 节点层。左缘层带标签 + 右上图例。
 */
import {
  ClockCircleOutlined,
  DatabaseOutlined,
  FundOutlined,
  GlobalOutlined,
  LoadingOutlined,
  CheckCircleFilled,
  PauseCircleOutlined,
  ReadOutlined,
  VideoCameraOutlined,
} from '@ant-design/icons'
import { Empty, Spin, Tag, Typography } from 'antd'
import type { ReactNode } from 'react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import type { AgentOverviewItem } from '@ai-invest/shared'

import { useCeleryQueues } from '@/hooks/useCeleryQueues'
import { useSystemStatus } from '@/hooks/useSystemStatus'

import { buildHubEdges } from './hubEdges'
import type { HubEdge } from './hubEdges'
import { layoutLayers } from './hubLayout'
import type { Point, StationId } from './hubLayout'

import { InfraLayerNodes } from './InfraLayer'
import { StateBadge } from './StateBadge'

const STATION_META: Record<StationId, { label: string; desc: string; icon: ReactNode }> = {
  kb: { label: '知识库', desc: '方法论基座', icon: <DatabaseOutlined /> },
  review: { label: '复盘数据', desc: 'AI 复盘 / 归因', icon: <ReadOutlined /> },
  news: { label: '资讯中心', desc: '电报 / 公告', icon: <GlobalOutlined /> },
  sentiment: { label: '大V情绪', desc: '抖音情绪分析', icon: <VideoCameraOutlined /> },
  paper: { label: '模拟盘交易', desc: '掘金仿真柜台', icon: <FundOutlined /> },
}

const EDGE_COLOR: Record<HubEdge['kind'], string> = {
  'plan-input': '#38bdf8',
  methodology: '#a855f7',
  account: '#faad14',
  upstream: '#8c8c8c',
}

const BAND_LABELS = [
  { y: 0.16, text: 'AGENT 运行' },
  { y: 0.46, text: '资源系统' },
  { y: 0.74, text: '基础设施' },
] as const

function useElementDims<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [dims, setDims] = useState({ width: 0, height: 0 })
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const observer = new ResizeObserver((entries) => {
      const rect = entries[0]?.contentRect
      if (rect) setDims({ width: rect.width, height: rect.height })
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])
  return { ref, dims }
}

function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(
    () => window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  )
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    const onChange = () => setReduced(mq.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])
  return reduced
}

/** 背景：科技网格 + conic 扫描线（页面唯一 rAF，reduced-motion 时单帧）。 */
function HubBackgroundCanvas() {
  const { ref, dims } = useElementDims<HTMLDivElement>()
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const container = ref.current
    const canvas = canvasRef.current
    if (!container || !canvas || dims.width === 0) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const dpr = window.devicePixelRatio || 1
    canvas.width = Math.max(1, Math.round(dims.width * dpr))
    canvas.height = Math.max(1, Math.round(dims.height * dpr))
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

    const width = dims.width
    const height = dims.height
    const cx = width / 2
    const cy = height / 2

    const drawFrame = (angle: number) => {
      ctx.clearRect(0, 0, width, height)
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)'
      ctx.beginPath()
      for (let x = 0.5; x < width; x += 48) {
        ctx.moveTo(x, 0)
        ctx.lineTo(x, height)
      }
      for (let y = 0.5; y < height; y += 48) {
        ctx.moveTo(0, y)
        ctx.lineTo(width, y)
      }
      ctx.stroke()

      // 各层带淡横线（分层语义）
      ctx.strokeStyle = 'rgba(148, 163, 184, 0.07)'
      for (const frac of [0.08, 0.3, 0.62, 0.85]) {
        ctx.beginPath()
        ctx.moveTo(0, height * frac)
        ctx.lineTo(width, height * frac)
        ctx.stroke()
      }

      const r = Math.min(width * 0.3, height * 0.45)
      const gradient = ctx.createConicGradient(angle, cx, cy)
      gradient.addColorStop(0, 'rgba(56, 189, 248, 0.1)')
      gradient.addColorStop(0.1, 'rgba(56, 189, 248, 0.02)')
      gradient.addColorStop(0.14, 'rgba(56, 189, 248, 0)')
      gradient.addColorStop(1, 'rgba(56, 189, 248, 0)')
      ctx.beginPath()
      ctx.moveTo(cx, cy)
      ctx.arc(cx, cy, r, 0, Math.PI * 2)
      ctx.fillStyle = gradient
      ctx.fill()
    }

    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      drawFrame(0)
      return
    }
    let raf = 0
    const start = performance.now()
    const render = (now: number) => {
      drawFrame(((now - start) / 1000 / 6) * Math.PI * 2)
      raf = requestAnimationFrame(render)
    }
    raf = requestAnimationFrame(render)
    return () => cancelAnimationFrame(raf)
  }, [ref, dims])

  return (
    <div ref={ref} className="absolute inset-0 overflow-hidden">
      <canvas ref={canvasRef} className="block" />
    </div>
  )
}

function edgePath(from: Point, to: Point): string {
  const mx = (from.x + to.x) / 2
  const my = (from.y + to.y) / 2
  const dx = to.x - from.x
  const dy = to.y - from.y
  return `M ${from.x} ${from.y} Q ${mx - dy * 0.12} ${my + dx * 0.12} ${to.x} ${to.y}`
}

function EdgeLayer({
  edges,
  stations,
  agentPoints,
  animated,
}: {
  edges: HubEdge[]
  stations: Record<StationId, Point>
  agentPoints: Map<string, Point>
  animated: boolean
}) {
  return (
    <svg
      className="pointer-events-none absolute inset-0"
      role="img"
      aria-label="Agent 与资源系统数据流"
    >
      <style>{`
        @keyframes hub-dash { to { stroke-dashoffset: -24; } }
        .hub-edge-fast { stroke-dasharray: 7 5; animation: hub-dash 0.9s linear infinite; }
      `}</style>
      {edges.map((edge) => {
        const from = stations[edge.from]
        const to = edge.toAgent ? agentPoints.get(edge.toAgent) : stations.review
        if (!from || !to) return null
        const color = EDGE_COLOR[edge.kind]
        const dashClass = animated && edge.speed === 'fast' ? 'hub-edge-fast' : undefined
        return (
          <g key={edge.id}>
            <path
              d={edgePath(from, to)}
              fill="none"
              className={dashClass}
              stroke={color}
              strokeOpacity={edge.opacity}
              strokeWidth={edge.speed === 'still' ? 1 : 1.5}
            />
            {animated && edge.speed === 'fast' && (
              <circle r={2.6} fill={color} opacity={0.9}>
                <animateMotion dur="2.2s" repeatCount="indefinite" path={edgePath(from, to)} />
              </circle>
            )}
          </g>
        )
      })}
    </svg>
  )
}

function ResourceStation({ id, point }: { id: StationId; point: Point }) {
  const meta = STATION_META[id]
  return (
    <div
      className="absolute -translate-x-1/2 -translate-y-1/2"
      style={{ left: point.x, top: point.y }}
    >
      <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-[#0b1220]/80 px-2.5 py-1.5 backdrop-blur-sm">
        <span className="inline-flex size-6 items-center justify-center rounded-lg bg-white/[0.06] text-sm text-sky-300">
          {meta.icon}
        </span>
        <span className="leading-tight">
          <Typography.Text strong className="block text-xs">
            {meta.label}
          </Typography.Text>
          <span className="block text-[10px] text-white/45">{meta.desc}</span>
        </span>
      </div>
    </div>
  )
}

function AgentUnit({ item, point }: { item: AgentOverviewItem; point: Point }) {
  const navigate = useNavigate()
  const { profile } = item
  const off = item.runtimeState === 'off'
  return (
    <button
      type="button"
      onClick={() => !off && void navigate(`/trading-agent/${profile.agentKey}`)}
      className={`absolute min-w-[136px] -translate-x-1/2 -translate-y-1/2 rounded-xl border px-3 py-2 text-left transition-colors ${
        off
          ? 'cursor-default border-white/5 bg-white/[0.02] opacity-55'
          : 'cursor-pointer border-white/10 bg-white/[0.04] hover:border-white/30'
      }`}
      style={{ left: point.x, top: point.y }}
    >
      <span className="flex items-center gap-2">
        <span
          className={`inline-block size-2.5 rounded-full ${item.runtimeState === 'working' ? 'animate-pulse' : ''}`}
          style={{ backgroundColor: profile.accentColor, boxShadow: `0 0 8px ${profile.accentColor}` }}
        />
        <Typography.Text strong className="text-xs">
          {profile.name}
        </Typography.Text>
      </span>
      <span className="mt-1 block">
        <StateBadge state={item.runtimeState} label={item.stateLabel} />
      </span>
      {!off && (
        <span className="mt-1 flex gap-1">
          <Tag className="!m-0 !px-1.5 !text-[10px] !leading-4">计划 {item.planCount}</Tag>
          <Tag className="!m-0 !px-1.5 !text-[10px] !leading-4">自选 {item.selectionCount}</Tag>
        </span>
      )}
    </button>
  )
}

function HubLegend() {
  return (
    <div className="pointer-events-none absolute right-3 top-3 rounded-lg border border-white/10 bg-black/50 px-3 py-2 text-[10px] leading-relaxed text-white/60 backdrop-blur-sm">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5">
        <span className="inline-flex items-center gap-1 text-sky-300">
          <LoadingOutlined /> 作业中
        </span>
        <span className="inline-flex items-center gap-1 text-green-400">
          <CheckCircleFilled /> 今日已产出
        </span>
        <span className="inline-flex items-center gap-1">
          <ClockCircleOutlined /> 待命
        </span>
        <span className="inline-flex items-center gap-1 text-white/35">
          <PauseCircleOutlined /> 未启用
        </span>
      </div>
      <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5">
        <span className="text-sky-300">━ 计划输入</span>
        <span className="text-purple-400">━ 方法论注入</span>
        <span className="text-amber-400">━ 账户交易</span>
        <span>━ 汇入复盘</span>
      </div>
      <div className="mt-1 text-white/40">基建灯：绿=正常 红=异常 · 小方框=Celery 任务（hover 看详情）</div>
    </div>
  )
}

export function AgentHubStage({
  items,
  isLoading,
}: {
  items: AgentOverviewItem[]
  isLoading: boolean
}) {
  const { ref, dims } = useElementDims<HTMLDivElement>()
  const reducedMotion = usePrefersReducedMotion()
  const { data: systemStatus } = useSystemStatus()
  const { data: celeryQueues } = useCeleryQueues()

  const layout = useMemo(() => {
    const queueCount = (celeryQueues?.queues ?? []).length
    return layoutLayers(dims.width, dims.height, items.length, queueCount)
  }, [dims, items.length, celeryQueues])
  const edges = useMemo(() => buildHubEdges(items), [items])
  const agentPoints = useMemo(
    () => new Map(items.map((item, i) => [item.profile.agentKey, layout.agents[i]])),
    [items, layout],
  )
  const ready = dims.width > 0 && dims.height > 0

  return (
    <div ref={ref} className="relative h-full w-full overflow-hidden">
      <HubBackgroundCanvas />
      {ready && (
        <>
          <EdgeLayer
            edges={edges}
            stations={layout.stations}
            agentPoints={agentPoints}
            animated={!reducedMotion}
          />
          <div className="absolute inset-0">
            {BAND_LABELS.map(({ y, text }) => (
              <span
                key={text}
                className="absolute text-[10px] tracking-widest text-white/30"
                style={{ left: 8, top: `${y * 100}%`, transform: 'translateY(-50%)' }}
              >
                {text}
              </span>
            ))}
            {items.map((item, i) => (
              <AgentUnit key={item.profile.agentKey} item={item} point={layout.agents[i]} />
            ))}
            {(Object.keys(STATION_META) as StationId[]).map((id) => (
              <ResourceStation key={id} id={id} point={layout.stations[id]} />
            ))}
            <InfraLayerNodes
              systemStatus={systemStatus}
              celeryQueues={celeryQueues}
              points={layout.infra}
              queuePoints={layout.queues}
            />
          </div>
        </>
      )}
      <HubLegend />
      {isLoading && items.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center">
          <Spin />
        </div>
      )}
      {!isLoading && items.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center">
          <Empty description="暂无注册的 Agent" />
        </div>
      )}
    </div>
  )
}
