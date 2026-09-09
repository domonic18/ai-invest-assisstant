import { Card, Spin, Tag, Typography } from 'antd'

import type { ChainAlert } from '@ai-invest/shared'

import { useChainAlerts } from '@/hooks/useChain'

const ALERT_TYPE_COLORS: Record<ChainAlert['alertType'], string> = {
  财报异动: 'orange',
  评级调整: 'geekblue',
  技术突破: 'cyan',
  格局变化: 'purple',
  政策催化: 'red',
}

const SEVERITY_META: Record<number, { color: string; label: string }> = {
  3: { color: '#f5222d', label: '高' },
  2: { color: '#fa8c16', label: '中' },
  1: { color: '#52c41a', label: '低' },
}

function severityMeta(severity: number) {
  return SEVERITY_META[severity] ?? SEVERITY_META[1]
}

/** 产业链提醒面板：AI 归因的重大变化（按严重度排序），随选中行业联动。

 无提醒/加载中折叠为单行细条，避免空态占据版面。
 */
export function ChainAlertPanel({ industry }: { industry: string }) {
  const { data: alerts, isLoading } = useChainAlerts(industry)

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-solid border-[#23262d] bg-[#111318] px-4 py-2">
        <Typography.Text type="secondary" strong>
          产业链提醒
        </Typography.Text>
        <Spin size="small" />
      </div>
    )
  }

  if (!alerts?.length) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-solid border-[#23262d] bg-[#111318] px-4 py-2">
        <Typography.Text type="secondary" strong>
          产业链提醒
        </Typography.Text>
        <Typography.Text type="secondary" className="text-xs">
          暂无提醒
        </Typography.Text>
      </div>
    )
  }

  return (
    <Card title="产业链提醒" variant="borderless">
      <div className="space-y-4">
        {alerts.map((alert) => {
            const severity = severityMeta(alert.severity)
            return (
              <div
                key={`${alert.alertType}-${alert.title}-${alert.signalDate}`}
                className="pb-3 border-b border-gray-800 last:border-b-0 last:pb-0"
              >
                <div className="flex items-center gap-2 flex-wrap">
                  <Tag color={ALERT_TYPE_COLORS[alert.alertType] ?? 'default'} className="!m-0">
                    {alert.alertType}
                  </Tag>
                  <span
                    className="inline-flex items-center gap-1 text-[11px]"
                    style={{ color: severity.color }}
                  >
                    <span
                      className="inline-block w-1.5 h-1.5 rounded-full"
                      style={{ backgroundColor: severity.color }}
                    />
                    {severity.label}
                  </span>
                  <Typography.Text className="text-xs font-medium flex-1 min-w-0 truncate">
                    {alert.title}
                  </Typography.Text>
                  <span className="text-[11px] text-gray-500 font-mono shrink-0">
                    {alert.signalDate}
                  </span>
                </div>
                {alert.description && (
                  <Typography.Paragraph className="!mb-0 mt-1.5 text-xs text-gray-400 whitespace-pre-line">
                    {alert.description}
                  </Typography.Paragraph>
                )}
                {(alert.affectedSegments.length > 0 || alert.relatedStockCodes.length > 0) && (
                  <div className="mt-1.5 flex items-center gap-2 flex-wrap text-[11px] text-gray-500">
                    {alert.affectedSegments.map((segment) => (
                      <Tag key={segment} className="!m-0 !text-[11px] !px-1.5 !py-0">
                        {segment}
                      </Tag>
                    ))}
                    {alert.relatedStockCodes.length > 0 && (
                      <span>相关标的: {alert.relatedStockCodes.join('、')}</span>
                    )}
                  </div>
                )}
              </div>
            )
        })}
      </div>
    </Card>
  )
}
