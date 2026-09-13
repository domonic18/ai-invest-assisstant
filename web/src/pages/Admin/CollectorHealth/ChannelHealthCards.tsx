import { Card, Typography } from 'antd'

import { getSourceLabel } from '@/utils/collectorTaskLabels'
import type { ApiCollectorChannelHealthItem } from '@ai-invest/shared'

import { CAUSE_OPTIONS, rateText } from './constants'

interface ChannelHealthPanelProps {
  channels: ApiCollectorChannelHealthItem[]
  loading?: boolean
  activeCause: string | null
  onCauseClick: (cause: string) => void
}

function channelDotColor(channel: ApiCollectorChannelHealthItem): string {
  const rate = channel.successRate7d
  if (channel.faultCount > 0 || (rate != null && rate < 0.8)) return '#f85149'
  if (rate == null || rate < 0.9) return '#d29922'
  return '#2ea043'
}

/** 渠道健康（timeline 列表）+ 错误归因分布（chips，点击过滤明细表）。 */
export function ChannelHealthPanel({
  channels,
  loading,
  activeCause,
  onCauseClick,
}: ChannelHealthPanelProps) {
  const totals = new Map<string, number>()
  const faultCauses = new Set<string>()
  for (const channel of channels) {
    if (channel.faultCount > 0) {
      for (const cause of Object.keys(channel.causes)) faultCauses.add(cause)
    }
    for (const [cause, count] of Object.entries(channel.causes)) {
      totals.set(cause, (totals.get(cause) ?? 0) + count)
    }
  }

  return (
    <div className="space-y-4">
      <Card size="small" title="渠道健康（7 天）" loading={loading}>
        {channels.length === 0 ? (
          <Typography.Text type="secondary">暂无快照数据，点击「立即检测」生成</Typography.Text>
        ) : (
          <div>
            {channels.map((channel) => (
              <div
                key={channel.source}
                className="flex items-start gap-3 border-b border-white/10 py-2.5 text-[13px] last:border-b-0"
              >
                <span
                  className="mt-[7px] inline-block h-2 w-2 flex-shrink-0 rounded-full"
                  style={{ background: channelDotColor(channel) }}
                />
                <div>
                  <div className="font-semibold">{getSourceLabel(channel.source)}</div>
                  <div className="mt-0.5 text-xs text-gray-400">
                    {channel.domainCount} 域 · {channel.instanceCount} 实例
                    {channel.successRate7d != null && ` · 7d ${rateText(channel.successRate7d)}`}
                    {channel.faultCount > 0 && (
                      <span className="ml-1.5" style={{ color: '#f85149' }}>
                        故障 {channel.faultCount}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card size="small" title="错误归因分布（7 天）" loading={loading}>
        <div className="flex flex-wrap gap-1.5">
          {CAUSE_OPTIONS.map(({ value, label }) => {
            const count = totals.get(value) ?? 0
            const active = activeCause === value
            const hot = count > 0 && faultCauses.has(value)
            const clickable = count > 0
            return (
              <span
                key={value}
                className={clickable ? 'cursor-pointer rounded-full px-2 py-0.5 text-[11px]' : 'rounded-full px-2 py-0.5 text-[11px]'}
                style={
                  active
                    ? { background: '#f85149', color: '#fff' }
                    : hot
                      ? { background: 'rgba(248, 81, 73, 0.12)', color: '#f85149' }
                      : { background: 'rgba(128, 128, 128, 0.12)', color: '#6b7280' }
                }
                onClick={clickable ? () => onCauseClick(value) : undefined}
              >
                {label} · {count}
              </span>
            )
          })}
        </div>
        <div className="mt-3 text-xs text-gray-400">
          点击归因类目可过滤任务明细；归因由 error_msg 模式匹配（详见需求文档 4.3）
        </div>
      </Card>
    </div>
  )
}
