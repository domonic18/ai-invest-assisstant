import { ReloadOutlined } from '@ant-design/icons'
import { Button, Empty, List, Skeleton, Typography } from 'antd'

import { useResearch } from '@/hooks/useResearch'
import type { ResearchReport } from '@ai-invest/shared'

interface StockResearchProps {
  data: ReturnType<typeof useResearch>['data']
  isLoading: boolean
  isError: boolean
  onRetry: () => void
}

export function StockResearch({ data, isLoading, isError, onRetry }: StockResearchProps) {
  if (isLoading) {
    return (
      <div className="py-2">
        <Skeleton active paragraph={{ rows: 4 }} />
      </div>
    )
  }

  if (isError) {
    return (
      <div className="py-4 flex flex-col items-start gap-2">
        <Typography.Text type="danger" className="text-xs">
          研报加载失败
        </Typography.Text>
        <Button size="small" icon={<ReloadOutlined />} onClick={onRetry}>
          重试
        </Button>
      </div>
    )
  }

  if (!data?.items.length) {
    return <Empty description="暂无相关研报" image={Empty.PRESENTED_IMAGE_SIMPLE} />
  }

  return (
    <List
      dataSource={data.items}
      renderItem={(item: ResearchReport) => (
        <List.Item className="!border-b-[#23262e]">
          <List.Item.Meta
            title={<span className="text-[#d1d4dc] text-sm">{item.title}</span>}
            description={
              <div className="space-y-1">
                <span className="text-xs text-[#8c8c8c]">
                  {item.source || '未知来源'} · {item.publishDate || '-'}
                </span>
                {item.summary && (
                  <Typography.Paragraph className="!text-xs text-[#8c8c8c] !mb-0">
                    {item.summary}
                  </Typography.Paragraph>
                )}
              </div>
            }
          />
        </List.Item>
      )}
    />
  )
}
