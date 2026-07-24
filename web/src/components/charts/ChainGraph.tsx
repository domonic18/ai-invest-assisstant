import { FullscreenExitOutlined, FullscreenOutlined } from '@ant-design/icons'
import G6 from '@antv/g6'
import type { IGroup, ModelConfig } from '@antv/g6'
import { useEffect, useRef, useState } from 'react'

import type { ChainEdge, ChainNode } from '@ai-invest/shared'

import {
  BAND_STYLES,
  NODE_TYPE_COLORS,
  NODE_TYPE_LABELS,
  buildSignalBadges,
  edgeStyleByCriticality,
  strengthToLineWidth,
  techBarrierColor,
  techBarrierLabel,
  truncateLabel,
} from './chainGraphStyle'

interface ChainGraphProps {
  nodes: ChainNode[]
  edges: ChainEdge[]
  onNodeClick?: (nodeName: string) => void
}

const NODE_WIDTH = 210
const NODE_HEIGHT = 132
const HALF_W = NODE_WIDTH / 2
const HALF_H = NODE_HEIGHT / 2

const BAND_HEIGHT = 30
const BAND_GAP = 12
const BAND_PAD_X = 24
const BAND_GROUP_NAME = 'chain-bands'

const TEXT_PRIMARY = '#1f2937'
const TEXT_SECONDARY = '#6b7280'

G6.registerNode(
  'chain-node',
  {
    draw(cfg: ModelConfig | undefined, group: IGroup | undefined) {
      const data = cfg?.nodeData as ChainNode
      const color = NODE_TYPE_COLORS[data.type]
      const left = -HALF_W
      const keyShape = group!.addShape('rect', {
        attrs: {
          x: left,
          y: -HALF_H,
          width: NODE_WIDTH,
          height: NODE_HEIGHT,
          radius: 8,
          fill: '#ffffff',
          stroke: color,
          lineWidth: 2,
          shadowColor: 'rgba(0,0,0,0.15)',
          shadowBlur: 4,
          shadowOffsetY: 1,
        },
        name: 'chain-node-box',
      })
      group!.addShape('text', {
        attrs: {
          x: 0,
          y: -HALF_H + 18,
          text: truncateLabel(data.name, 12),
          fill: TEXT_PRIMARY,
          fontSize: 13,
          fontWeight: 700,
          textAlign: 'center',
          textBaseline: 'middle',
        },
        name: 'chain-node-title',
      })
      group!.addShape('text', {
        attrs: {
          x: 0,
          y: -HALF_H + 35,
          text: truncateLabel(data.description || '', 24),
          fill: TEXT_SECONDARY,
          fontSize: 9,
          textAlign: 'center',
          textBaseline: 'middle',
        },
        name: 'chain-node-subtitle',
      })
      group!.addShape('line', {
        attrs: {
          x1: left + 15,
          y1: -HALF_H + 44,
          x2: HALF_W - 15,
          y2: -HALF_H + 44,
          stroke: '#e2e8f0',
          lineWidth: 1,
        },
        name: 'chain-node-divider',
      })
      const metricStyle = {
        x: left + 15,
        fontSize: 9,
        fill: TEXT_SECONDARY,
        textBaseline: 'middle',
      } as const
      const margin = data.avgGrossMargin !== null ? `${data.avgGrossMargin}%` : '—'
      const localization =
        data.localizationRate !== null ? `${data.localizationRate}%` : '—'
      group!.addShape('text', {
        attrs: {
          ...metricStyle,
          y: -HALF_H + 57,
          text: `毛利率 ${margin} | 国产化率 ${localization}`,
        },
        name: 'chain-node-metrics',
      })
      group!.addShape('text', {
        attrs: {
          ...metricStyle,
          y: -HALF_H + 70,
          text: `壁垒 ${techBarrierLabel(data.techBarrier)}`,
          fill: techBarrierColor(data.techBarrier),
        },
        name: 'chain-node-barrier',
      })
      const companyNames = data.companies
        .slice(0, 3)
        .map((company) => company.name)
        .join(' ')
      group!.addShape('text', {
        attrs: {
          ...metricStyle,
          y: -HALF_H + 83,
          text: truncateLabel(`核心: ${companyNames}`, 26),
        },
        name: 'chain-node-companies',
      })
      buildSignalBadges(data).forEach((badge, index) => {
        const pillY = -HALF_H + 90 + index * 14
        group!.addShape('rect', {
          attrs: {
            x: left + 2,
            y: pillY,
            width: NODE_WIDTH - 4,
            height: 12,
            radius: 3,
            fill: badge.fill,
          },
          name: `chain-node-badge-bg-${index}`,
        })
        group!.addShape('text', {
          attrs: {
            x: 0,
            y: pillY + 6,
            text: truncateLabel(`${badge.icon} ${badge.text}`, 22),
            fill: badge.textFill,
            fontSize: 8,
            textAlign: 'center',
            textBaseline: 'middle',
          },
          name: `chain-node-badge-text-${index}`,
        })
      })
      return keyShape
    },
  },
  'rect',
)

/** 在各类环节节点群上方绘制全宽分栏标题条（上/中/下游自上而下）。 */
function drawChainBands(graph: InstanceType<typeof G6.Graph>) {
  const rootGroup = graph.get('group') as IGroup
  rootGroup
    .find((element) => element.get('name') === BAND_GROUP_NAME)
    ?.remove()

  const extents: Partial<
    Record<ChainNode['type'], { minY: number; maxY: number }>
  > = {}
  let minX = Infinity
  let maxX = -Infinity
  for (const item of graph.getNodes()) {
    const model = item.getModel()
    const data = model.nodeData as ChainNode | undefined
    if (!data || model.x === undefined || model.y === undefined) continue
    const bucket = extents[data.type] ?? { minY: Infinity, maxY: -Infinity }
    bucket.minY = Math.min(bucket.minY, model.y)
    bucket.maxY = Math.max(bucket.maxY, model.y)
    extents[data.type] = bucket
    minX = Math.min(minX, model.x)
    maxX = Math.max(maxX, model.x)
  }
  if (minX === Infinity) return

  const bandGroup = rootGroup.addGroup({ name: BAND_GROUP_NAME })
  const bandX = minX - HALF_W - BAND_PAD_X
  const bandWidth = maxX - minX + 2 * (HALF_W + BAND_PAD_X)
  const orderedTypes: ChainNode['type'][] = ['upstream', 'midstream', 'downstream']
  for (const type of orderedTypes) {
    const bucket = extents[type]
    if (!bucket) continue
    const style = BAND_STYLES[type]
    const bandY = bucket.minY - HALF_H - BAND_GAP - BAND_HEIGHT
    bandGroup.addShape('rect', {
      attrs: {
        x: bandX,
        y: bandY,
        width: bandWidth,
        height: BAND_HEIGHT,
        radius: 6,
        fill: style.fill,
        fillOpacity: 0.7,
      },
      name: `chain-band-${type}`,
    })
    bandGroup.addShape('text', {
      attrs: {
        x: bandX + bandWidth / 2,
        y: bandY + BAND_HEIGHT / 2,
        text: `◆ ${NODE_TYPE_LABELS[type]}`,
        fill: style.text,
        fontSize: 13,
        fontWeight: 700,
        textAlign: 'center',
        textBaseline: 'middle',
      },
      name: `chain-band-title-${type}`,
    })
  }
  bandGroup.toBack()
}

export function ChainGraph({ nodes, edges, onNodeClick }: ChainGraphProps) {
  const wrapperRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const graphRef = useRef<InstanceType<typeof G6.Graph> | null>(null)
  const onNodeClickRef = useRef(onNodeClick)
  const [isFullscreen, setIsFullscreen] = useState(false)
  onNodeClickRef.current = onNodeClick

  useEffect(() => {
    const onFullscreenChange = () => {
      const active = document.fullscreenElement === wrapperRef.current
      setIsFullscreen(active)
      // 等 fullscreen 样式生效后再同步画布尺寸并复位视野
      requestAnimationFrame(() => {
        const graph = graphRef.current
        const container = containerRef.current
        if (!graph || graph.get('destroyed') || !container) return
        graph.changeSize(container.clientWidth, container.clientHeight)
        graph.fitView(20)
      })
    }
    document.addEventListener('fullscreenchange', onFullscreenChange)
    return () => document.removeEventListener('fullscreenchange', onFullscreenChange)
  }, [])

  const toggleFullscreen = () => {
    if (document.fullscreenElement) {
      void document.exitFullscreen()
    } else {
      void wrapperRef.current?.requestFullscreen()
    }
  }

  useEffect(() => {
    if (!containerRef.current) return

    const width = containerRef.current.clientWidth
    const height = containerRef.current.clientHeight || 700

    const graph = new G6.Graph({
      container: containerRef.current,
      width,
      height,
      // dagre 布局在 g6-pc 中是异步执行的，必须在布局完成后（success 回调内）fitView，
      // 因此用构造配置而不是 render 后手动调用
      fitView: true,
      fitViewPadding: 20,
      layout: {
        type: 'dagre',
        rankdir: 'TB',
        nodesep: 20,
        ranksep: 80,
      },
      defaultNode: {
        type: 'chain-node',
        size: [NODE_WIDTH, NODE_HEIGHT],
      },
      defaultEdge: {
        type: 'line',
        labelCfg: {
          style: {
            fill: TEXT_SECONDARY,
            fontSize: 11,
          },
        },
      },
      modes: {
        default: [
          'drag-canvas',
          // sensitivity 默认为 2，滚轮缩放过于灵敏；降为 1 使缩放更平滑
          { type: 'zoom-canvas', sensitivity: 1, minZoom: 0.2, maxZoom: 3 },
          'drag-node',
        ],
      },
    })

    graph.on('node:click', (evt) => {
      const model = evt.item?.getModel()
      if (model?.id && onNodeClickRef.current) {
        onNodeClickRef.current(String(model.id))
      }
    })

    graphRef.current = graph

    return () => {
      graph.destroy()
      graphRef.current = null
    }
  }, [])

  useEffect(() => {
    const graph = graphRef.current
    if (!graph) return

    const g6Nodes = nodes.map((node) => ({
      id: node.name,
      nodeData: node,
    }))

    const g6Edges = edges.map((edge) => {
      const visual = edgeStyleByCriticality(edge.criticality)
      return {
        source: edge.source,
        target: edge.target,
        label: edge.relation,
        style: {
          stroke: visual.stroke,
          lineWidth: strengthToLineWidth(edge.strength),
          ...(visual.lineDash ? { lineDash: visual.lineDash } : {}),
          endArrow: {
            path: G6.Arrow.triangle(8, 10, 0),
            fill: visual.stroke,
          },
        },
        edgeData: edge,
      }
    })

    // afterlayout 在位置刷新后、构造配置 fitView 前触发：先画分栏条再统一 fitView，
    // 保证分栏条计入视野 bbox；changeData 的重新布局同样走此回调
    graph.once('afterlayout', () => {
      if (graph.get('destroyed')) return
      drawChainBands(graph)
      graph.fitView(20)
    })

    if (graph.getNodes().length > 0) {
      graph.changeData({ nodes: g6Nodes, edges: g6Edges })
    } else {
      graph.data({ nodes: g6Nodes, edges: g6Edges })
      graph.render()
    }
  }, [nodes, edges])

  return (
    <div
      ref={wrapperRef}
      className={
        isFullscreen ? 'relative w-full h-full bg-[#fafbfc] p-4' : 'relative w-full'
      }
    >
      <div
        ref={containerRef}
        className={`w-full bg-[#fafbfc] rounded-lg border border-[#e2e8f0] ${
          isFullscreen ? 'h-full' : 'h-[700px]'
        }`}
      />
      <button
        type="button"
        onClick={toggleFullscreen}
        title={isFullscreen ? '退出全屏' : '全屏查看'}
        className="absolute right-3 top-3 z-10 flex h-8 w-8 items-center justify-center rounded-md border border-[#e2e8f0] bg-white text-[#6b7280] shadow-sm hover:text-[#1f2937]"
      >
        {isFullscreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
      </button>
    </div>
  )
}
