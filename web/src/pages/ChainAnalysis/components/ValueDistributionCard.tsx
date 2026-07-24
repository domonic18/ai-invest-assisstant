import { Col, Row, Statistic } from 'antd'
import ReactECharts from 'echarts-for-react'

import type { ChainNode, ChainValueDistribution } from '@ai-invest/shared'

interface ValueDistributionCardProps {
  nodes: ChainNode[]
  valueDistribution: ChainValueDistribution | null
}

export function ValueDistributionCard({
  nodes,
  valueDistribution,
}: ValueDistributionCardProps) {
  const ranked = nodes
    .filter((node) => node.avgGrossMargin !== null)
    .slice()
    .sort((a, b) => (b.avgGrossMargin ?? 0) - (a.avgGrossMargin ?? 0))

  const option = {
    backgroundColor: 'transparent',
    animation: false,
    grid: { left: 90, right: 50, top: 10, bottom: 30 },
    tooltip: { trigger: 'axis' as const },
    xAxis: {
      type: 'value' as const,
      axisLabel: { color: '#8c8c8c', fontSize: 10 },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
    },
    yAxis: {
      type: 'category' as const,
      inverse: true,
      data: ranked.map((node) => node.name),
      axisLabel: { color: '#8c8c8c', fontSize: 10 },
      axisLine: { lineStyle: { color: '#3a3f4b' } },
    },
    series: [
      {
        type: 'bar' as const,
        data: ranked.map((node) => node.avgGrossMargin),
        itemStyle: { color: '#5e6ad2' },
        label: {
          show: true,
          position: 'right' as const,
          color: '#8c8c8c',
          fontSize: 10,
          formatter: '{c}%',
        },
      },
    ],
  }

  return (
    <div>
      {valueDistribution && (
        <Row gutter={16} className="mb-2">
          <Col span={12}>
            <Statistic
              title="最高毛利环节"
              value={valueDistribution.highestMarginSegment ?? '—'}
              suffix={
                valueDistribution.highestMarginValue !== null
                  ? `${valueDistribution.highestMarginValue}%`
                  : ''
              }
              valueStyle={{ fontSize: 16 }}
            />
          </Col>
          <Col span={12}>
            <Statistic
              title="最低毛利环节"
              value={valueDistribution.lowestMarginSegment ?? '—'}
              suffix={
                valueDistribution.lowestMarginValue !== null
                  ? `${valueDistribution.lowestMarginValue}%`
                  : ''
              }
              valueStyle={{ fontSize: 16 }}
            />
          </Col>
        </Row>
      )}
      {ranked.length > 0 ? (
        <ReactECharts option={option} style={{ height: 260 }} />
      ) : (
        <div className="flex h-40 items-center justify-center text-gray-500">
          暂无毛利率数据
        </div>
      )}
    </div>
  )
}
