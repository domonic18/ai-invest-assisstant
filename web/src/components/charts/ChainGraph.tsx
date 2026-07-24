import G6 from '@antv/g6'
import type { IGroup, ModelConfig } from '@antv/g6'
import { useEffect, useRef } from 'react'

import type { ChainEdge, ChainNode } from '@ai-invest/shared'

import {
  NODE_TYPE_COLORS,
  NODE_TYPE_LABELS,
  edgeStyleByCriticality,
  marginToOpacity,
  strengthToLineWidth,
} from './chainGraphStyle'

interface ChainGraphProps {
  nodes: ChainNode[]
  edges: ChainEdge[]
  onNodeClick?: (nodeName: string) => void
}

const NODE_WIDTH = 180
const NODE_HEIGHT = 88
const HALF_W = NODE_WIDTH / 2
const HALF_H = NODE_HEIGHT / 2

const BAND_PAD_X = 12
const BAND_TOP_PAD = 70
const BAND_BOTTOM_PAD = 24
const BAND_GROUP_NAME = 'chain-bands'

function truncateLabel(text: string, maxChars: number): string {
  return text.length > maxChars ? `${text.slice(0, maxChars - 1)}…` : text
}

G6.registerNode(
  'chain-node',
  {
    draw(cfg: ModelConfig | undefined, group: IGroup | undefined) {
      const data = cfg?.nodeData as ChainNode
      const color = NODE_TYPE_COLORS[data.type]
      const keyShape = group!.addShape('rect', {
        attrs: {
          x: -HALF_W,
          y: -HALF_H,
          width: NODE_WIDTH,
          height: NODE_HEIGHT,
          radius: 8,
          fill: color,
          fillOpacity: marginToOpacity(data.avgGrossMargin),
          stroke: color,
          lineWidth: 1,
        },
        name: 'chain-node-box',
      })
      group!.addShape('text', {
        attrs: {
          x: 0,
          y: -16,
          text: truncateLabel(data.name, 11),
          fill: '#e6e6e6',
          fontSize: 14,
          fontWeight: 600,
          textAlign: 'center',
          textBaseline: 'middle',
        },
        name: 'chain-node-title',
      })
      const metricStyle = {
        fill: '#9ca3af',
        fontSize: 11,
        textAlign: 'center',
        textBaseline: 'middle',
      } as const
      group!.addShape('text', {
        attrs: {
          ...metricStyle,
          x: 0,
          y: 8,
          text:
            data.avgGrossMargin !== null ? `毛利率 ${data.avgGrossMargin}%` : '毛利率 —',
        },
        name: 'chain-node-margin',
      })
      group!.addShape('text', {
        attrs: {
          ...metricStyle,
          x: 0,
          y: 27,
          text:
            data.localizationRate !== null
              ? `国产化率 ${data.localizationRate}%`
              : '国产化率 —',
        },
        name: 'chain-node-localization',
      })
      group!.addShape('text', {
        attrs: {
          x: HALF_W - 8,
          y: -HALF_H + 12,
          text: `${data.companies.length} 标的`,
          fill: color,
          fontSize: 10,
          textAlign: 'right',
          textBaseline: 'middle',
        },
        name: 'chain-node-badge',
      })
      return keyShape
    },
  },
  'rect',
)

/** 按上/中/下游分栏绘制背景带与标题；重复调用前会移除旧分栏。 */
function drawChainBands(graph: InstanceType<typeof G6.Graph>) {
  const rootGroup = graph.get('group') as IGroup
  rootGroup
    .find((element) => element.get('name') === BAND_GROUP_NAME)
    ?.remove()

  const extents: Partial<Record<ChainNode['type'], { minX: number; maxX: number }>> = {}
  let minY = Infinity
  let maxY = -Infinity
  for (const item of graph.getNodes()) {
    const model = item.getModel()
    const data = model.nodeData as ChainNode | undefined
    if (!data || model.x === undefined || model.y === undefined) continue
    const bucket = extents[data.type] ?? { minX: Infinity, maxX: -Infinity }
    bucket.minX = Math.min(bucket.minX, model.x)
    bucket.maxX = Math.max(bucket.maxX, model.x)
    extents[data.type] = bucket
    minY = Math.min(minY, model.y)
    maxY = Math.max(maxY, model.y)
  }
  if (minY === Infinity) return

  const bandGroup = rootGroup.addGroup({ name: BAND_GROUP_NAME })
  const bandTop = minY - HALF_H - BAND_TOP_PAD
  const bandHeight = maxY - minY + 2 * HALF_H + BAND_TOP_PAD + BAND_BOTTOM_PAD
  const orderedTypes: ChainNode['type'][] = ['upstream', 'midstream', 'downstream']
  for (const type of orderedTypes) {
    const bucket = extents[type]
    if (!bucket) continue
    const color = NODE_TYPE_COLORS[type]
    bandGroup.addShape('rect', {
      attrs: {
        x: bucket.minX - HALF_W - BAND_PAD_X,
        y: bandTop,
        width: bucket.maxX - bucket.minX + 2 * (HALF_W + BAND_PAD_X),
        height: bandHeight,
        radius: 12,
        fill: color,
        fillOpacity: 0.04,
      },
      name: `chain-band-${type}`,
    })
    bandGroup.addShape('text', {
      attrs: {
        x: (bucket.minX + bucket.maxX) / 2,
        y: bandTop + 26,
        text: NODE_TYPE_LABELS[type],
        fill: color,
        fontSize: 14,
        fontWeight: 600,
        textAlign: 'center',
        textBaseline: 'middle',
        opacity: 0.8,
      },
      name: `chain-band-title-${type}`,
    })
  }
  bandGroup.toBack()
}

export function ChainGraph({ nodes, edges, onNodeClick }: ChainGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const graphRef = useRef<InstanceType<typeof G6.Graph> | null>(null)
  const onNodeClickRef = useRef(onNodeClick)
  onNodeClickRef.current = onNodeClick

  useEffect(() => {
    if (!containerRef.current) return

    const width = containerRef.current.clientWidth
    const height = containerRef.current.clientHeight || 500

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
        rankdir: 'LR',
        nodesep: 30,
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
            fill: '#9ca3af',
            fontSize: 12,
          },
        },
      },
      modes: {
        default: ['drag-canvas', 'zoom-canvas', 'drag-node'],
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

    // afterlayout 在位置刷新后、构造配置 fitView 前触发：先画分栏带再统一 fitView，
    // 保证分栏带计入视野 bbox；changeData 的重新布局同样走此回调
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

  return <div ref={containerRef} className="w-full h-[500px] bg-[#111318] rounded-lg" />
}
