import { CloseOutlined, MenuUnfoldOutlined } from '@ant-design/icons'
import { Button, Card, Space } from 'antd'

import { ChainGraph } from '@/components/charts/ChainGraph'
import type { ChainEdge, ChainNode } from '@ai-invest/shared'

import { NodeDetailCard } from './NodeDetailCard'

interface ChainGraphPanelProps {
  nodes: ChainNode[]
  edges: ChainEdge[]
  selectedNode: ChainNode | null
  detailCollapsed: boolean
  onNodeClick: (nodeName: string) => void
  onExpandDetail: () => void
  onCollapseDetail: () => void
  onCloseDetail: () => void
}

export function ChainGraphPanel({
  nodes,
  edges,
  selectedNode,
  detailCollapsed,
  onNodeClick,
  onExpandDetail,
  onCollapseDetail,
  onCloseDetail,
}: ChainGraphPanelProps) {
  return (
    <Card variant="borderless" bodyStyle={{ padding: 0 }} className="overflow-hidden">
      <div className="relative">
        <ChainGraph nodes={nodes} edges={edges} onNodeClick={onNodeClick} />
        {selectedNode && detailCollapsed && (
          <Button
            size="small"
            icon={<MenuUnfoldOutlined />}
            onClick={onExpandDetail}
            className="!absolute right-12 top-3 z-10"
          >
            节点详情
          </Button>
        )}
        {selectedNode && !detailCollapsed && (
          <Card
            size="small"
            title={selectedNode.name}
            className="!absolute right-12 top-3 bottom-3 w-80 z-10 shadow-xl flex flex-col [&_.ant-card-body]:flex-1 [&_.ant-card-body]:overflow-y-auto"
            extra={
              <Space size={4}>
                <Button
                  type="text"
                  size="small"
                  icon={<MenuUnfoldOutlined rotate={180} />}
                  title="收起"
                  onClick={onCollapseDetail}
                />
                <Button
                  type="text"
                  size="small"
                  icon={<CloseOutlined />}
                  title="关闭"
                  onClick={onCloseDetail}
                />
              </Space>
            }
          >
            <NodeDetailCard node={selectedNode} />
          </Card>
        )}
      </div>
    </Card>
  )
}
