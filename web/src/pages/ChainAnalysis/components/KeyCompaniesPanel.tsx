import { Empty, List, Progress, Space, Tag, Typography } from 'antd'

import type { KeyCompanySummary } from '@ai-invest/shared'

interface KeyCompaniesPanelProps {
  companies: KeyCompanySummary[]
}

export function KeyCompaniesPanel({ companies }: KeyCompaniesPanelProps) {
  if (companies.length === 0) {
    return (
      <Empty
        description={<span className="text-[#8c8c8c]">暂无核心标的</span>}
        className="py-10"
      />
    )
  }

  const ranked = companies
    .slice()
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
    .slice(0, 10)

  return (
    <List
      size="small"
      dataSource={ranked}
      renderItem={(item, index) => (
        <List.Item className="!px-0">
          <Space className="w-full items-center" size={12}>
            <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#23262e] text-xs text-[#8c8c8c]">
              {index + 1}
            </div>
            <div className="min-w-0 flex-1">
              <Space wrap size={6}>
                <Typography.Text strong className="text-[#d1d4dc]">
                  {item.name}
                </Typography.Text>
                <Typography.Text type="secondary" className="text-xs">
                  {item.code}
                </Typography.Text>
                {item.chainPosition && <Tag className="text-xs">{item.chainPosition}</Tag>}
              </Space>
            </div>
            {item.score !== null && (
              <Progress
                percent={item.score}
                size="small"
                style={{ width: 80 }}
                strokeColor="#6366f1"
                showInfo={false}
              />
            )}
          </Space>
        </List.Item>
      )}
    />
  )
}
