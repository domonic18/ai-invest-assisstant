import G6 from '@antv/g6'
import { useEffect, useRef } from 'react'

import type { ChainEdge, ChainNode } from '@ai-invest/shared'

interface ChainGraphProps {
  nodes: ChainNode[]
  edges: ChainEdge[]
  onNodeClick?: (nodeName: string) => void
}

const NODE_COLORS: Record<ChainNode['type'], string> = {
  upstream: '#58a6ff',
  midstream: '#5e6ad2',
  downstream: '#2ea043',
}

export function ChainGraph({ nodes, edges, onNodeClick }: ChainGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const graphRef = useRef<InstanceType<typeof G6.Graph> | null>(null)

  useEffect(() => {
    if (!containerRef.current) return

    const width = containerRef.current.clientWidth
    const height = containerRef.current.clientHeight || 500

    const graph = new G6.Graph({
      container: containerRef.current,
      width,
      height,
      layout: {
        type: 'dagre',
        rankdir: 'LR',
        nodesep: 60,
        ranksep: 100,
      },
      defaultNode: {
        type: 'rect',
        size: [160, 80],
        style: {
          radius: 8,
          fill: '#181a21',
          stroke: '#5e6ad2',
          lineWidth: 1,
        },
        labelCfg: {
          style: {
            fill: '#e6e6e6',
            fontSize: 14,
            fontWeight: 500,
          },
        },
      },
      defaultEdge: {
        type: 'line',
        style: {
          stroke: '#5e6ad2',
          lineWidth: 2,
          endArrow: {
            path: G6.Arrow.triangle(8, 10, 0),
            fill: '#5e6ad2',
          },
        },
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
      if (model?.id && onNodeClick) {
        onNodeClick(String(model.id))
      }
    })

    graphRef.current = graph

    return () => {
      graph.destroy()
      graphRef.current = null
    }
  }, [onNodeClick])

  useEffect(() => {
    const graph = graphRef.current
    if (!graph) return

    const g6Nodes = nodes.map((node) => ({
      id: node.name,
      label: node.name,
      style: {
        stroke: NODE_COLORS[node.type],
      },
      nodeData: node,
    }))

    const g6Edges = edges.map((edge) => ({
      source: edge.source,
      target: edge.target,
      label: edge.relation,
      edgeData: edge,
    }))

    graph.data({ nodes: g6Nodes, edges: g6Edges })
    graph.render()
    graph.fitView(20)
  }, [nodes, edges])

  return <div ref={containerRef} className="w-full h-[500px] bg-[#111318] rounded-lg" />
}
