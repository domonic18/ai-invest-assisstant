import { Tabs, Typography } from 'antd'

import { useNewsChannels } from '@/hooks/useNewsChannels'

import { ChannelMonitorBar } from './components/ChannelMonitorBar'
import { GlobalStatsBar } from './components/GlobalStatsBar'
import { NewsFeedView } from './components/NewsFeedView'
import { PlaceholderView } from './components/PlaceholderView'

/** 资讯中心：渠道监控 + 今日统计 + 三视图（本迭代仅实时电报有数据）。 */
export function News() {
  const { data } = useNewsChannels()
  const channels = data?.channels ?? []
  const anyLive = channels.some((channel) => channel.status === 'live')
  const allDelayed =
    channels.length > 0 && channels.every((channel) => channel.status === 'delayed')

  return (
    <div className="space-y-4">
      <div>
        <Typography.Title level={4} className="!mb-0">
          资讯中心
        </Typography.Title>
        <div className="flex items-center gap-1.5 text-xs opacity-60 mt-1">
          <span
            className={`inline-block size-[7px] rounded-full ${
              anyLive
                ? 'bg-red-500 animate-pulse'
                : allDelayed
                  ? 'bg-amber-500 animate-pulse'
                  : 'bg-gray-400'
            }`}
          />
          {anyLive
            ? '实时采集中 · 全渠道聚合 / AI 重要度分级'
            : allDelayed
              ? '全部渠道延迟，请检查采集任务'
              : '渠道状态监测中'}
        </div>
      </div>

      <ChannelMonitorBar channels={channels} />
      <GlobalStatsBar stats={data?.stats} />

      <Tabs
        defaultActiveKey="live"
        items={[
          {
            key: 'live',
            label: '实时电报',
            children: <NewsFeedView channels={channels} />,
          },
          {
            key: 'focus',
            label: '重点与跟踪',
            children: (
              <PlaceholderView
                title="重点与跟踪（迭代 4 接入）"
                description="AI 重要度评分 TOP 资讯与同一事件的故事线聚合跟踪"
              />
            ),
          },
          {
            key: 'topic',
            label: '热点主题',
            children: (
              <PlaceholderView
                title="热点主题（迭代 4 接入）"
                description="当日资讯聚类生成主题，联动板块行情与资金流验证"
              />
            ),
          },
        ]}
      />
    </div>
  )
}
