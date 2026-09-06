import { Empty, Spin, Tag } from 'antd'
import dayjs from 'dayjs'

import type { TelegraphItem } from '@ai-invest/shared'

interface HotTimelineProps {
  items?: TelegraphItem[]
  loading?: boolean
}

/** 实时热点时间线：财联社电报按发布时间倒序（10s 准实时），原型竖线 + 圆点样式。 */
export function HotTimeline({ items, loading }: HotTimelineProps) {
  if (loading && !items?.length) {
    return <div className="flex justify-center py-16"><Spin /></div>
  }
  if (!items?.length) {
    return <Empty description="暂无电报" image={Empty.PRESENTED_IMAGE_SIMPLE} />
  }
  return (
    <div className="h-[440px] overflow-y-auto pr-1">
      <div className="relative pl-6">
        {/* 原型 timeline 竖线：贯穿内容区左侧 */}
        <div className="absolute bottom-1 left-[7px] top-1 w-0.5 bg-gray-700/80" />
        {items.map((item) => (
          <div key={item.clsMsgId} className="relative pb-4 last:pb-0">
            <span className="absolute -left-[21px] top-[5px] h-2.5 w-2.5 rounded-full border-2 border-white bg-[#5e6ad2]" />
            <div className="text-[11px] text-gray-500">
              {dayjs(item.publishTime).format('HH:mm')}
            </div>
            <div className="mt-0.5 text-[13px] font-medium leading-snug text-gray-100">
              {item.title ?? item.content}
            </div>
            {item.title && item.content && (
              <div className="mt-0.5 line-clamp-2 text-[11px] leading-snug text-gray-400">
                {item.content}
              </div>
            )}
            {item.importance === 3 && (
              <div className="mt-1">
                <Tag color="red" className="!mr-0">热门</Tag>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
