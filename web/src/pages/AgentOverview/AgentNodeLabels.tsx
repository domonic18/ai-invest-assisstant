/**
 * 雷达节点 HTML 标签覆盖层：仅 active 节点名卡（点击进详情）。
 * 像素定位（left/top = radarLayout 输出的 px 坐标），与 Canvas 层共用
 * 同一容器尺寸，杜绝双层错位（D28）。
 */
import { Button, Tag } from 'antd'
import { useNavigate } from 'react-router-dom'

import type { RadarNode } from './radarLayout'

export function AgentNodeLabels({ nodes }: { nodes: RadarNode[] }) {
  const navigate = useNavigate()

  return (
    <div className="pointer-events-none absolute inset-0">
      {nodes.map((node) => (
        <div
          key={node.agentKey}
          className="absolute"
          style={{
            left: node.x,
            top: node.y,
            transform: 'translate(-50%, -50%) translate(0, 30px)',
          }}
        >
          <div className="pointer-events-auto">
            <Button
              size="small"
              className="!rounded-lg !border-white/10 !bg-white/[0.03]"
              onClick={() => void navigate(`/trading-agent/${node.agentKey}`)}
            >
              <span className="inline-flex items-center gap-1.5">
                <span
                  className="inline-block size-2 rounded-full"
                  style={{ backgroundColor: node.accentColor }}
                />
                {node.name}
                <Tag color="processing" className="!mr-0">
                  工作中
                </Tag>
              </span>
            </Button>
          </div>
        </div>
      ))}
    </div>
  )
}
