import { Card, Col, Row, Tag, Typography } from 'antd'

import { getSourceLabel } from '@/utils/collectorTaskLabels'
import type { ApiCollectorChannelHealthItem } from '@ai-invest/shared'

import { causeLabel, rateText } from './constants'

interface ChannelHealthCardsProps {
  channels: ApiCollectorChannelHealthItem[]
  loading?: boolean
  activeCause: string | null
  onCauseClick: (cause: string) => void
}

export function ChannelHealthCards({
  channels,
  loading,
  activeCause,
  onCauseClick,
}: ChannelHealthCardsProps) {
  return (
    <Card size="small" title="渠道视图" loading={loading}>
      <Row gutter={[12, 12]}>
        {channels.map((channel) => {
          const rate = channel.successRate7d
          return (
            <Col xs={24} sm={12} lg={8} xl={6} key={channel.source}>
              <div className="h-full rounded border border-gray-200 p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium">{getSourceLabel(channel.source)}</span>
                  <Typography.Text type="secondary" className="text-xs">
                    {channel.domainCount} 域 / {channel.instanceCount} 实例
                  </Typography.Text>
                </div>
                <div className="text-xs text-gray-500 mb-2">
                  7d 成功率：
                  <span
                    style={{
                      color:
                        rate == null
                          ? undefined
                          : rate < 0.8
                            ? '#f85149'
                            : rate < 0.9
                              ? '#d29922'
                              : '#2ea043',
                    }}
                  >
                    {rateText(rate)}
                  </span>
                  {channel.faultCount > 0 && (
                    <span className="ml-2" style={{ color: '#f85149' }}>
                      故障 {channel.faultCount}
                    </span>
                  )}
                </div>
                <div className="flex flex-wrap gap-1">
                  {Object.entries(channel.causes).map(([cause, count]) => (
                    <Tag
                      key={cause}
                      className="cursor-pointer"
                      color={activeCause === cause ? 'red' : 'default'}
                      onClick={() => onCauseClick(cause)}
                    >
                      {causeLabel(cause)} × {count}
                    </Tag>
                  ))}
                  {Object.keys(channel.causes).length === 0 && (
                    <span className="text-xs text-gray-400">无归因错误</span>
                  )}
                </div>
              </div>
            </Col>
          )
        })}
        {channels.length === 0 && !loading && (
          <Col span={24}>
            <Typography.Text type="secondary">
              暂无快照数据，点击「立即检测」生成
            </Typography.Text>
          </Col>
        )}
      </Row>
    </Card>
  )
}
