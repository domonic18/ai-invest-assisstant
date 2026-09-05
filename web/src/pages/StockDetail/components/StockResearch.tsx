import { ReloadOutlined, RobotOutlined } from '@ant-design/icons'
import { Button, Empty, Skeleton } from 'antd'

import { useResearch } from '@/hooks/useResearch'
import type { ResearchReport } from '@ai-invest/shared'

interface StockResearchProps {
  data: ReturnType<typeof useResearch>['data']
  isLoading: boolean
  isError: boolean
  onRetry: () => void
}

export function StockResearch({ data, isLoading, isError, onRetry }: StockResearchProps) {
  const header = (
    <div className="flex items-center justify-between px-3.5 py-2.5 border-b border-[#23262d]">
      <span className="text-[13px] font-semibold text-[#f0f1f5]">相关研报</span>
      {data && (
        <span className="text-[11px] text-[#5c616e]">共 {data.total} 篇</span>
      )}
    </div>
  )

  if (isLoading) {
    return (
      <div>
        {header}
        <div className="px-3.5 py-3">
          <Skeleton active title={false} paragraph={{ rows: 4 }} />
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div>
        {header}
        <div className="px-3.5 py-3 flex items-center gap-2">
          <span className="text-xs text-[#f85149]">研报加载失败</span>
          <Button size="small" icon={<ReloadOutlined />} onClick={onRetry}>
            重试
          </Button>
        </div>
      </div>
    )
  }

  if (!data?.items.length) {
    return (
      <div>
        {header}
        <Empty
          className="py-4"
          description="暂无相关研报"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      </div>
    )
  }

  return (
    <div>
      {header}
      <div className="px-3.5 pb-3 pt-2.5">
        {data.items.map((item: ResearchReport) => {
          const broker = item.broker || item.source
          const hasAiText = Boolean(item.summary)
          return (
            <div
              key={item.id}
              className="px-3 py-2.5 mb-2 bg-[#111318] border border-[#23262d] rounded-md transition-colors last:mb-0 hover:border-[rgba(94,106,210,0.25)]"
            >
              <div className="text-[13px] font-semibold leading-snug text-[#f0f1f5] mb-1.5">
                {item.title}
              </div>
              <div className="flex items-center flex-wrap gap-x-2 gap-y-0.5 mb-1.5 text-[11px]">
                {broker && <span className="text-[#8a8f98]">{broker}</span>}
                {item.publishDate && (
                  <span className="font-mono text-[#5c616e]">{item.publishDate}</span>
                )}
                {item.rating && (
                  <span className="px-1 py-px rounded bg-[#181a21] border border-[#23262d] text-[#5c616e]">
                    {item.rating}
                  </span>
                )}
                {item.hasSummary && !hasAiText && (
                  <span className="text-[#5e6ad2]">AI 已解读</span>
                )}
              </div>
              {item.summary && (
                <div className="rounded-md bg-[#181a21] border-l-2 border-[#5e6ad2] px-2.5 py-2">
                  <div className="flex items-center gap-1 text-[10px] font-semibold text-[#5e6ad2] mb-1">
                    <RobotOutlined style={{ fontSize: 11 }} />
                    AI 解读要点
                  </div>
                  <p className="m-0 text-xs text-[#8a8f98] leading-[1.6] line-clamp-4">
                    {item.summary}
                  </p>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
