import { ReloadOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Skeleton, Space, Tag, Typography, theme } from 'antd'
import type { ServiceStatusItem, SystemStatus } from '@ai-invest/shared'

import { useSystemStatus } from '@/hooks/useSystemStatus'
import { formatDateTime } from '@/utils/formatters'

function StatusDot({ up, color, size = 'h-2.5 w-2.5' }: { up: boolean; color: string; size?: string }) {
  return (
    <span className={`relative flex flex-none ${size}`}>
      {up && (
        <span
          className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-60"
          style={{ backgroundColor: color }}
        />
      )}
      <span className={`relative inline-flex rounded-full ${size}`} style={{ backgroundColor: color }} />
    </span>
  )
}

function OverallBanner({ status, onRefresh, refreshing }: { status: SystemStatus; onRefresh: () => void; refreshing: boolean }) {
  const { token } = theme.useToken()
  const allUp = status.overall === 'operational'
  const color = allUp ? token.colorSuccess : token.colorWarning
  const upCount = status.items.filter((i) => i.status === 'up').length

  return (
    <Card variant="borderless">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <StatusDot up={allUp} color={color} size="h-3.5 w-3.5" />
          <div>
            <Typography.Title level={4} className="!mb-1" style={{ color }}>
              {allUp ? '系统运行正常' : '部分服务异常'}
            </Typography.Title>
            <Typography.Text type="secondary">
              {upCount}/{status.items.length} 项依赖正常 · 每 30 秒自动刷新
            </Typography.Text>
          </div>
        </div>
        <Space>
          <Typography.Text type="secondary">最后检测 {formatDateTime(status.checkedAt)}</Typography.Text>
          <Button icon={<ReloadOutlined spin={refreshing} />} onClick={onRefresh}>
            刷新
          </Button>
        </Space>
      </div>
    </Card>
  )
}

function ServiceCard({ item }: { item: ServiceStatusItem }) {
  const { token } = theme.useToken()
  const up = item.status === 'up'
  const color = up ? token.colorSuccess : token.colorError

  return (
    <Card variant="borderless" className="h-full">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2.5">
          <StatusDot up={up} color={color} />
          <Typography.Text strong>{item.name}</Typography.Text>
        </div>
        {up && item.latencyMs != null && (
          <Tag style={{ fontFamily: 'monospace', marginInlineEnd: 0 }}>{item.latencyMs} ms</Tag>
        )}
      </div>
      <div className="mt-3 min-w-0">
        {up ? (
          <Typography.Text type="secondary" className="!text-xs" ellipsis={{ tooltip: item.detail }}>
            {item.detail || '连接正常'}
          </Typography.Text>
        ) : (
          <Typography.Text type="danger" className="!text-xs" ellipsis={{ tooltip: item.error }}>
            {item.error || '连接失败'}
          </Typography.Text>
        )}
      </div>
    </Card>
  )
}

export function SystemStatus() {
  const { data, isLoading, error, refetch, isFetching } = useSystemStatus()

  return (
    <div className="space-y-6">
      <div>
        <Typography.Title level={4} className="!mb-1">
          服务状态
        </Typography.Title>
        <Typography.Text type="secondary">系统运行所需依赖服务的实时连接状态</Typography.Text>
      </div>

      {isLoading ? (
        <Card variant="borderless">
          <Skeleton active paragraph={{ rows: 6 }} />
        </Card>
      ) : error || !data ? (
        <Alert
          type="error"
          showIcon
          message="服务状态加载失败"
          description={error instanceof Error ? error.message : undefined}
          action={
            <Button size="small" danger onClick={() => refetch()}>
              重试
            </Button>
          }
        />
      ) : (
        <>
          <OverallBanner status={data} onRefresh={() => refetch()} refreshing={isFetching} />
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {data.items.map((item) => (
              <ServiceCard key={item.key} item={item} />
            ))}
          </div>
        </>
      )}
    </div>
  )
}
