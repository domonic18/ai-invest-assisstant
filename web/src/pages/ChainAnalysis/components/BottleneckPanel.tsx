import { Card, Empty, Space, Tag, Typography } from 'antd'

import type { ChainNode } from '@ai-invest/shared'

interface BottleneckPanelProps {
  nodes: ChainNode[]
}

function bottleneckColor(node: ChainNode): string {
  if (node.localizationRate !== null && node.localizationRate < 50) return 'error'
  return 'warning'
}

export function BottleneckPanel({ nodes }: BottleneckPanelProps) {
  const bottlenecks = nodes.filter((node) => node.bottleneckIndicators.length > 0)

  if (bottlenecks.length === 0) {
    return <Empty description="未识别到明显瓶颈环节" />
  }

  return (
    <Space direction="vertical" className="w-full">
      {bottlenecks.map((node) => (
        <Card key={node.name} size="small" variant="outlined">
          <Space direction="vertical" size={4} className="w-full">
            <Space>
              <Typography.Text strong>{node.name}</Typography.Text>
              <Tag color={bottleneckColor(node)}>
                {node.localizationRate !== null
                  ? `国产化率 ${node.localizationRate}%`
                  : '国产化率未知'}
              </Tag>
              {node.techBarrier && <Tag>技术壁垒 {node.techBarrier}</Tag>}
            </Space>
            <Space wrap size={4}>
              {node.bottleneckIndicators.map((indicator) => (
                <Tag key={indicator} color={bottleneckColor(node)}>
                  {indicator}
                </Tag>
              ))}
            </Space>
          </Space>
        </Card>
      ))}
    </Space>
  )
}
