import { Descriptions, List, Space, Statistic, Tag, Typography } from 'antd'

import type { ChainNode } from '@ai-invest/shared'
import { useColorScheme } from '@/stores/settings'
import { riseColorSoft } from '@/utils/formatters'

interface NodeDetailCardProps {
  node: ChainNode | null
}

const TYPE_LABELS: Record<ChainNode['type'], string> = {
  upstream: '上游',
  midstream: '中游',
  downstream: '下游',
}

function metricItem(label: string, value: number | null, suffix = '%') {
  return (
    <Descriptions.Item label={label} key={label}>
      {value !== null ? `${value}${suffix}` : '—'}
    </Descriptions.Item>
  )
}

export function NodeDetailCard({ node }: NodeDetailCardProps) {
  useColorScheme()
  if (!node) {
    return (
      <Typography.Text type="secondary">点击图谱中的节点查看详情</Typography.Text>
    )
  }

  return (
    <Space direction="vertical" className="w-full" size={12}>
      <Space>
        <Typography.Text strong className="text-base">
          {node.name}
        </Typography.Text>
        <Tag>{TYPE_LABELS[node.type]}</Tag>
        {node.techBarrier && <Tag color="purple">技术壁垒 {node.techBarrier}</Tag>}
      </Space>

      {node.description && (
        <Typography.Paragraph type="secondary" className="!mb-0">
          {node.description}
        </Typography.Paragraph>
      )}

      <Descriptions size="small" column={2}>
        {metricItem('平均毛利率', node.avgGrossMargin)}
        {metricItem('营收增长', node.revenueGrowth)}
        {metricItem('研发占比', node.rdRatio)}
        {metricItem('议价能力', node.bargainingPower, '')}
        {metricItem('国产化率', node.localizationRate)}
      </Descriptions>

      {node.bottleneckIndicators.length > 0 && (
        <div>
          <Typography.Text type="secondary">瓶颈因素：</Typography.Text>
          <Space wrap size={4} className="ml-1">
            {node.bottleneckIndicators.map((item) => (
              <Tag key={item} color="warning">
                {item}
              </Tag>
            ))}
          </Space>
        </div>
      )}

      {node.recentBreakthroughs.length > 0 && (
        <div>
          <Typography.Text type="secondary">近期突破：</Typography.Text>
          <List
            size="small"
            dataSource={node.recentBreakthroughs}
            renderItem={(item) => (
              <List.Item className="!py-1">
                <Typography.Text className={riseColorSoft()}>{item}</Typography.Text>
              </List.Item>
            )}
          />
        </div>
      )}

      <div>
        <Typography.Text type="secondary">代表公司：</Typography.Text>
        <List
          size="small"
          dataSource={node.companies}
          renderItem={(company) => (
            <List.Item className="!py-1">
              {company.name} ({company.code})
            </List.Item>
          )}
        />
      </div>

      <Statistic
        title="节点公司数"
        value={node.companies.length}
        valueStyle={{ fontSize: 14 }}
      />
    </Space>
  )
}
