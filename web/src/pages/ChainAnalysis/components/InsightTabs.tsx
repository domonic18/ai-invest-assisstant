import { Empty, Space, Tabs } from 'antd'

import type { ChainNode, ChainOpportunity, ChainRisk } from '@ai-invest/shared'

import { InsightCard } from './InsightCard'

interface InsightTabsProps {
  opportunities: ChainOpportunity[]
  risks: ChainRisk[]
  nodes: ChainNode[]
}

export function InsightTabs({ opportunities, risks, nodes }: InsightTabsProps) {
  const bottlenecks = nodes
    .filter((node) => node.bottleneckIndicators.length > 0)
    .flatMap((node) =>
      node.bottleneckIndicators.map((indicator) => ({
        nodeName: node.name,
        indicator,
        localizationRate: node.localizationRate,
        techBarrier: node.techBarrier,
      })),
    )

  const hasAny =
    opportunities.length > 0 || risks.length > 0 || bottlenecks.length > 0

  if (!hasAny) {
    return (
      <Empty
        description={
          <span className="text-[#8c8c8c]">暂无机会、风险与瓶颈洞察</span>
        }
        className="py-10"
      />
    )
  }

  const items = [
    {
      key: 'opportunities',
      label: `机会 (${opportunities.length})`,
      children: opportunities.length > 0 ? (
        <Space direction="vertical" className="w-full" size={12}>
          {opportunities.map((item, index) => (
            <InsightCard
              key={`opp-${index}`}
              type="opportunity"
              title={item.title}
              description={item.description}
              level={item.confidence as 'high' | 'medium' | 'low' | null}
              levelLabel="置信"
              relatedSegment={item.relatedSegment}
            />
          ))}
        </Space>
      ) : (
        <Empty description="暂无机会洞察" className="py-10" />
      ),
    },
    {
      key: 'risks',
      label: `风险 (${risks.length})`,
      children: risks.length > 0 ? (
        <Space direction="vertical" className="w-full" size={12}>
          {risks.map((item, index) => (
            <InsightCard
              key={`risk-${index}`}
              type="risk"
              title={item.title}
              description={item.description}
              level={item.severity as 'high' | 'medium' | 'low' | null}
              levelLabel="严重"
              relatedSegment={item.relatedSegment}
            />
          ))}
        </Space>
      ) : (
        <Empty description="暂无风险洞察" className="py-10" />
      ),
    },
    {
      key: 'bottlenecks',
      label: `瓶颈 (${bottlenecks.length})`,
      children: bottlenecks.length > 0 ? (
        <Space direction="vertical" className="w-full" size={12}>
          {bottlenecks.map((item, index) => (
            <InsightCard
              key={`bn-${index}`}
              type="bottleneck"
              title={item.indicator}
              description={`${item.nodeName}${
                item.localizationRate !== null
                  ? ` · 国产化率 ${item.localizationRate}%`
                  : ''
              }${item.techBarrier ? ` · 技术壁垒 ${item.techBarrier}` : ''}`}
              relatedSegment={item.nodeName}
            />
          ))}
        </Space>
      ) : (
        <Empty description="暂无瓶颈环节" className="py-10" />
      ),
    },
  ]

  return (
    <Tabs
      defaultActiveKey="opportunities"
      items={items}
      className="chain-insight-tabs"
    />
  )
}
