import { Tooltip } from 'antd'
import dayjs from 'dayjs'

import type { ApiNewsChannel, NewsChannelStatus } from '@ai-invest/shared'

import { formatDateTime } from '@/utils/formatters'

/** 状态点/状态色按 status 映射（后端 statusText 为文案真相源，样式在前端）。 */
const STATUS_DOT_CLASS: Record<NewsChannelStatus, string> = {
  live: 'bg-red-500 animate-pulse',
  ok: 'bg-green-500',
  delayed: 'bg-amber-500 animate-pulse',
  batch: 'bg-blue-400',
}

const STATUS_TEXT_CLASS: Record<NewsChannelStatus, string> = {
  live: 'text-red-500',
  ok: 'opacity-60',
  delayed: 'text-amber-500',
  batch: 'text-blue-400',
}

function lagText(lagSeconds: number | null): string {
  if (lagSeconds === null) return ''
  if (lagSeconds < 60) return `${lagSeconds}s`
  return `${Math.round(lagSeconds / 60)}min`
}

/** 渠道监控条：按 /news/channels 响应渲染，卡数量随注册表增长，不写死。 */
export function ChannelMonitorBar({ channels }: { channels: ApiNewsChannel[] }) {
  if (channels.length === 0) return null
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-5 gap-3">
      {channels.map((channel) => (
        <div
          key={channel.key}
          className="rounded-lg border border-white/10 bg-white/[0.02] px-3.5 py-3"
        >
          <div className="flex items-center justify-between gap-2 mb-1">
            <span className="flex items-center gap-1.5 text-sm font-semibold min-w-0">
              <span
                className={`inline-block size-[7px] rounded-full shrink-0 ${STATUS_DOT_CLASS[channel.status]}`}
              />
              {channel.name}
            </span>
            <span className={`text-xs shrink-0 ${STATUS_TEXT_CLASS[channel.status]}`}>
              {channel.statusText}
            </span>
          </div>
          <div className="text-xs opacity-50 mb-2 truncate" title={channel.pollDesc}>
            {channel.pollDesc}
          </div>
          <div className="flex items-baseline justify-between gap-2 text-xs opacity-70">
            <span>
              今日 <b className="font-mono text-sm">{channel.todayCount}</b> 条
            </span>
            {channel.lastUpdatedAt && (
              <Tooltip
                title={`最后更新 ${formatDateTime(channel.lastUpdatedAt)}${
                  channel.lagSeconds !== null ? ` · 滞后 ${lagText(channel.lagSeconds)}` : ''
                }`}
              >
                <span className="font-mono text-xs opacity-60 whitespace-nowrap">
                  {dayjs(channel.lastUpdatedAt).format('HH:mm')}
                  {channel.lagSeconds !== null && ` · ${lagText(channel.lagSeconds)}`}
                </span>
              </Tooltip>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
