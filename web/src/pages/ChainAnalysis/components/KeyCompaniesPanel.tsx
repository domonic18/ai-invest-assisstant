import { Empty, List, Progress, Space, Tag, Typography } from 'antd'

import type { KeyCompanySummary } from '@ai-invest/shared'

interface KeyCompaniesPanelProps {
  companies: KeyCompanySummary[]
}

export function KeyCompaniesPanel({ companies }: KeyCompaniesPanelProps) {
  if (companies.length === 0) {
    return <Empty description="暂无核心标的" />
  }

  const ranked = companies
    .slice()
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))

  return (
    <List
      size="small"
      dataSource={ranked}
      renderItem={(item) => (
        <List.Item>
          <Space className="w-full justify-between" size={8}>
            <Space size={8}>
              <Typography.Text strong>{item.name}</Typography.Text>
              <Typography.Text type="secondary">{item.code}</Typography.Text>
              {item.chainPosition && <Tag>{item.chainPosition}</Tag>}
            </Space>
            {item.score !== null && (
              <Progress
                percent={item.score}
                size="small"
                style={{ width: 120 }}
                strokeColor="#5e6ad2"
              />
            )}
          </Space>
        </List.Item>
      )}
    />
  )
}
