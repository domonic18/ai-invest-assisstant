/**
 * 雷达节点 HTML 标签覆盖层：active 节点名卡（点击进详情）、ghost 节点
 * 点击弹策略简介卡（Popover，不可进入详情）。几何与画布共用 radarLayout。
 */
import { Button, Popover, Tag, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'

import type { RadarNode } from './radarLayout'

function GhostLabel({ node }: { node: RadarNode }) {
  return (
    <Popover
      trigger="click"
      title={
        <span className="inline-flex items-center gap-2">
          {node.name}
          <Tag color="default" className="!mr-0">
            即将上线
          </Tag>
        </span>
      }
      content={
        <div className="max-w-60 text-xs">
          <Typography.Paragraph type="secondary" className="!mb-1 text-xs">
            {node.tagline}
          </Typography.Paragraph>
          <Typography.Paragraph className="!mb-0 text-xs">{node.strategyDesc}</Typography.Paragraph>
        </div>
      }
    >
      <button
        type="button"
        className="cursor-pointer rounded-lg border border-white/10 bg-white/[0.03] px-2.5 py-1 opacity-60 transition-opacity hover:opacity-90"
      >
        <Typography.Text type="secondary" className="text-xs">
          {node.name}
        </Typography.Text>
      </button>
    </Popover>
  )
}

export function AgentNodeLabels({ nodes }: { nodes: RadarNode[] }) {
  const navigate = useNavigate()

  return (
    <div className="pointer-events-none absolute inset-0">
      {nodes.map((node) => (
        <div
          key={node.agentKey}
          className="absolute"
          style={{
            left: `${node.x * 100}%`,
            top: `${node.y * 100}%`,
            transform: 'translate(-50%, -50%) translate(0, 30px)',
          }}
        >
          <div className="pointer-events-auto">
            {node.ghost ? (
              <GhostLabel node={node} />
            ) : (
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
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
