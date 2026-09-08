import { BellOutlined } from '@ant-design/icons'
import { Button, Tabs, Typography } from 'antd'
import { useState } from 'react'

import { useNewsChannels } from '@/hooks/useNewsChannels'

import { ChannelMonitorBar } from './components/ChannelMonitorBar'
import { FocusView } from './components/FocusView'
import { GlobalStatsBar } from './components/GlobalStatsBar'
import { NewsFeedView } from './components/NewsFeedView'
import { SubscriptionDrawer } from './components/SubscriptionDrawer'
import { TopicView } from './components/TopicView'

/** 资讯中心：渠道监控 + 今日统计 + 三视图（电报/重点跟踪/热点主题）+ 我的订阅。 */
export function News() {
  const { data } = useNewsChannels()
  const [subDrawerOpen, setSubDrawerOpen] = useState(false)
  const channels = data?.channels ?? []
  const anyLive = channels.some((channel) => channel.status === 'live')
  const allDelayed =
    channels.length > 0 && channels.every((channel) => channel.status === 'delayed')

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
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
        <Button
          icon={<BellOutlined />}
          onClick={() => setSubDrawerOpen(true)}
        >
          我的订阅
        </Button>
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
            children: <FocusView />,
          },
          {
            key: 'topic',
            label: '热点主题',
            children: <TopicView />,
          },
        ]}
      />

      <SubscriptionDrawer open={subDrawerOpen} onClose={() => setSubDrawerOpen(false)} />
    </div>
  )
}
