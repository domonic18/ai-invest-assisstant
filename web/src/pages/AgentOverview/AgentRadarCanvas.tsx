/**
 * 贾维斯雷达画布（rAF Canvas2D）：科技网格底 + 雷达扫描线 + 中心市场核心 +
 * 椭圆轨道上的 active Agent 节点（脉冲光环）+ 核心↔节点数据粒子流。
 * DPR 适配 + ResizeObserver；节点几何来自 radarLayout（像素坐标，
 * 与 HTML 标签层共用同一份容器尺寸，D28 修复双层错位与越界裁剪）。
 */
import { useEffect, useRef } from 'react'

import type { RadarNode } from './radarLayout'

const CORE_COLOR = '#38bdf8'
const GRID_GAP = 48
const SWEEP_SECONDS = 6
const ORBIT_RX = 0.36
const ORBIT_RY = 0.32
const SWEEP_R = 0.42

/** hex → rgba 字符串（profile.accentColor 形如 #3b82f6）。 */
function rgba(hex: string, alpha: number): string {
  const value = hex.replace('#', '')
  const r = parseInt(value.slice(0, 2), 16)
  const g = parseInt(value.slice(2, 4), 16)
  const b = parseInt(value.slice(4, 6), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

function drawSweep(ctx: CanvasRenderingContext2D, cx: number, cy: number, r: number, angle: number) {
  const gradient = ctx.createConicGradient(angle, cx, cy)
  gradient.addColorStop(0, 'rgba(56, 189, 248, 0.22)')
  gradient.addColorStop(0.08, 'rgba(56, 189, 248, 0.03)')
  gradient.addColorStop(0.12, 'rgba(56, 189, 248, 0)')
  gradient.addColorStop(1, 'rgba(56, 189, 248, 0)')
  ctx.beginPath()
  ctx.moveTo(cx, cy)
  ctx.arc(cx, cy, r, 0, Math.PI * 2)
  ctx.fillStyle = gradient
  ctx.fill()
}

function drawCore(ctx: CanvasRenderingContext2D, cx: number, cy: number, t: number) {
  const pulse = 1 + 0.08 * Math.sin(t * 2)
  const glow = ctx.createRadialGradient(cx, cy, 2, cx, cy, 46 * pulse)
  glow.addColorStop(0, 'rgba(56, 189, 248, 0.5)')
  glow.addColorStop(0.5, 'rgba(56, 189, 248, 0.12)')
  glow.addColorStop(1, 'rgba(56, 189, 248, 0)')
  ctx.beginPath()
  ctx.arc(cx, cy, 46 * pulse, 0, Math.PI * 2)
  ctx.fillStyle = glow
  ctx.fill()

  ctx.beginPath()
  ctx.arc(cx, cy, 13 * pulse, 0, Math.PI * 2)
  ctx.fillStyle = CORE_COLOR
  ctx.fill()

  ctx.fillStyle = 'rgba(255, 255, 255, 0.55)'
  ctx.font = '11px system-ui, sans-serif'
  ctx.textAlign = 'center'
  ctx.fillText('市场核心', cx, cy + 32)
}

function drawOrbit(ctx: CanvasRenderingContext2D, cx: number, cy: number, rx: number, ry: number, alpha: number) {
  ctx.beginPath()
  ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2)
  ctx.strokeStyle = `rgba(148, 163, 184, ${alpha})`
  ctx.stroke()
}

export function AgentRadarCanvas({ nodes }: { nodes: RadarNode[] }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const nodesRef = useRef(nodes)
  nodesRef.current = nodes

  useEffect(() => {
    const container = containerRef.current
    const canvas = canvasRef.current
    if (!container || !canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let raf = 0
    let width = 0
    let height = 0

    const resize = () => {
      const dpr = window.devicePixelRatio || 1
      width = container.clientWidth
      height = container.clientHeight
      canvas.width = Math.max(1, Math.round(width * dpr))
      canvas.height = Math.max(1, Math.round(height * dpr))
      canvas.style.width = `${width}px`
      canvas.style.height = `${height}px`
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }
    resize()
    const observer = new ResizeObserver(resize)
    observer.observe(container)

    const start = performance.now()
    const render = (now: number) => {
      const t = (now - start) / 1000
      ctx.clearRect(0, 0, width, height)

      // 科技网格底
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)'
      ctx.lineWidth = 1
      ctx.beginPath()
      for (let x = 0.5; x < width; x += GRID_GAP) {
        ctx.moveTo(x, 0)
        ctx.lineTo(x, height)
      }
      for (let y = 0.5; y < height; y += GRID_GAP) {
        ctx.moveTo(0, y)
        ctx.lineTo(width, y)
      }
      ctx.stroke()

      const cx = width / 2
      const cy = height / 2

      // 椭圆轨道（与 radarLayout 同比例）+ 最外淡环
      drawOrbit(ctx, cx, cy, ORBIT_RX * width, ORBIT_RY * height, 0.1)
      drawOrbit(ctx, cx, cy, SWEEP_R * width, SWEEP_R * height, 0.05)

      drawSweep(
        ctx,
        cx,
        cy,
        Math.min(SWEEP_R * width, SWEEP_R * height),
        (t / SWEEP_SECONDS) * Math.PI * 2,
      )
      drawCore(ctx, cx, cy, t)

      for (const node of nodesRef.current) {
        const { x: nx, y: ny } = node

        // 核心↔节点连线 + 数据粒子流
        ctx.beginPath()
        ctx.moveTo(cx, cy)
        ctx.lineTo(nx, ny)
        ctx.strokeStyle = rgba(node.accentColor, 0.14)
        ctx.stroke()

        for (let i = 0; i < 2; i++) {
          const p = (t * 0.5 + i * 0.5) % 1
          const px = cx + (nx - cx) * p
          const py = cy + (ny - cy) * p
          ctx.beginPath()
          ctx.arc(px, py, 2.2, 0, Math.PI * 2)
          ctx.fillStyle = rgba(node.accentColor, 0.8 * (1 - Math.abs(p - 0.5)))
          ctx.fill()
        }

        // 节点本体 + busy 脉冲光环
        ctx.beginPath()
        ctx.arc(nx, ny, 9, 0, Math.PI * 2)
        ctx.fillStyle = rgba(node.accentColor, 0.9)
        ctx.fill()

        const ring = 12 + 5 * Math.sin(t * 3 + nx)
        ctx.beginPath()
        ctx.arc(nx, ny, ring, 0, Math.PI * 2)
        ctx.strokeStyle = rgba(node.accentColor, 0.35)
        ctx.stroke()
      }

      raf = requestAnimationFrame(render)
    }
    raf = requestAnimationFrame(render)

    return () => {
      cancelAnimationFrame(raf)
      observer.disconnect()
    }
  }, [])

  return (
    <div ref={containerRef} className="relative h-full w-full overflow-hidden">
      <canvas ref={canvasRef} className="block" />
    </div>
  )
}
