import { PlayCircleOutlined } from '@ant-design/icons'
import { Button, Table, Tag, Tooltip, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import { getSourceLabel, getTaskLabel } from '@/utils/collectorTaskLabels'
import { formatDateTime } from '@/utils/formatters'
import type { ApiCollectorHealthTaskItem } from '@ai-invest/shared'

import {
  causeLabel,
  domainGroupStats,
  domainLabel,
  lastSuccessText,
  rateText,
  ROLE_CHIP,
  STATUS_META,
  STATUS_ORDER,
} from './constants'

interface TaskHealthTableProps {
  tasks: ApiCollectorHealthTaskItem[]
  loading?: boolean
  rerunningTaskType: string | null
  onViewLogs: (taskType: string, source: string) => void
  onRerun: (taskType: string) => void
  onGotoChannels: () => void
}

const DOMAIN_ORDER = ['kline', 'quote', 'pool', 'fund-flow', 'news', 'fundamental', 'ai', 'other']

function rateColor(value: number): string {
  return value < 0.8 ? '#f85149' : value < 0.9 ? '#d29922' : '#2ea043'
}

/** 成功率 mini bar（原型 bar 结构：64px 轨道 + 阈值色填充 + 百分比）。 */
function RateBar({ value }: { value: number | null }) {
  if (value == null) return <span className="text-xs text-gray-400">-</span>
  const color = rateColor(value)
  return (
    <span className="inline-flex items-center gap-2">
      <span
        className="inline-block h-[5px] w-16 overflow-hidden rounded-full align-middle"
        style={{ background: 'rgba(128, 128, 128, 0.18)' }}
      >
        <span
          className="block h-full rounded-full"
          style={{ width: `${Math.min(100, Math.round(value * 100))}%`, background: color }}
        />
      </span>
      <span className="text-xs" style={{ color }}>
        {rateText(value)}
      </span>
    </span>
  )
}

function StatusTag({ status, reasons }: { status: string; reasons?: string[] }) {
  const meta = STATUS_META[status as keyof typeof STATUS_META]
  if (!meta) return status
  const tag = (
    <span
      className="inline-flex cursor-default items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium"
      style={{ background: meta.bg, color: meta.color }}
    >
      <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ background: meta.color }} />
      {meta.label}
    </span>
  )
  return reasons?.length ? <Tooltip title={reasons.join('；')}>{tag}</Tooltip> : tag
}

export function TaskHealthTable({
  tasks,
  loading,
  rerunningTaskType,
  onViewLogs,
  onRerun,
  onGotoChannels,
}: TaskHealthTableProps) {
  const columns: ColumnsType<ApiCollectorHealthTaskItem> = [
    {
      title: '任务实例',
      dataIndex: 'taskType',
      key: 'taskType',
      render: (_, record) => {
        const role = ROLE_CHIP[record.role]
        return (
          <div>
            <div>{getTaskLabel(record.taskType)}</div>
            <Typography.Text type="secondary" className="text-xs">
              {getSourceLabel(record.source)}
              {role && (
                <span
                  className="ml-1.5 rounded px-1 text-[10px] leading-4"
                  style={{ color: role.color, background: role.bg }}
                >
                  {role.label}
                </span>
              )}
            </Typography.Text>
          </div>
        )
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 96,
      render: (_, record) => <StatusTag status={record.status} reasons={record.reasons} />,
    },
    {
      title: '24h 成功率',
      dataIndex: 'successRate24h',
      key: 'successRate24h',
      width: 140,
      responsive: ['lg'],
      render: (value: number | null) => <RateBar value={value} />,
    },
    {
      title: '7d 成功率',
      dataIndex: 'successRate7d',
      key: 'successRate7d',
      width: 140,
      responsive: ['lg'],
      render: (value: number | null) => <RateBar value={value} />,
    },
    {
      title: '连败',
      dataIndex: 'consecutiveFailures',
      key: 'consecutiveFailures',
      width: 64,
      render: (value: number) => (value > 0 ? <b style={{ color: '#f85149' }}>{value}</b> : 0),
    },
    {
      title: '缺口窗口',
      dataIndex: 'windowsWithoutSuccess',
      key: 'windowsWithoutSuccess',
      width: 84,
      render: (value: number) => (value > 0 ? <span style={{ color: '#d29922' }}>{value}</span> : 0),
    },
    {
      title: '最近成功',
      dataIndex: 'lastSuccessAt',
      key: 'lastSuccessAt',
      width: 110,
      responsive: ['xl'],
      render: (value: string | null, record) => {
        const severe = record.status === 'critical' || record.status === 'silent'
        return (
          <Tooltip title={value ? formatDateTime(value) : undefined}>
            <span style={severe ? { color: '#f85149', fontWeight: 600 } : undefined}>
              {lastSuccessText(value)}
            </span>
          </Tooltip>
        )
      },
    },
    {
      title: '最近错误',
      dataIndex: 'lastErrorSummary',
      key: 'lastErrorSummary',
      width: 240,
      ellipsis: true,
      render: (_, record) =>
        record.lastErrorSummary ? (
          <Typography.Text type="danger" ellipsis={{ tooltip: record.lastErrorSummary }}>
            {causeLabel(record.lastErrorCause) && (
              <Tag className="mr-1">{causeLabel(record.lastErrorCause)}</Tag>
            )}
            {record.lastErrorSummary}
          </Typography.Text>
        ) : (
          '-'
        ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 170,
      render: (_, record) => (
        <div className="flex gap-1">
          <Button
            size="small"
            type="link"
            onClick={() => onViewLogs(record.taskType, record.source)}
          >
            日志
          </Button>
          {record.isActive !== false && record.status !== 'unconfigured' && (
            <Button
              size="small"
              type="link"
              icon={<PlayCircleOutlined />}
              loading={rerunningTaskType === record.taskType}
              onClick={() => onRerun(record.taskType)}
            >
              补跑
            </Button>
          )}
          <Button size="small" type="link" onClick={onGotoChannels}>
            渠道
          </Button>
        </div>
      ),
    },
  ]

  const stats = domainGroupStats(tasks)
  const domains = DOMAIN_ORDER.filter((d) => stats.some((s) => s.domain === d))

  return (
    <div className={loading ? 'opacity-60 transition-opacity' : undefined}>
      {domains.map((domain) => {
        const stat = stats.find((s) => s.domain === domain)!
        const items = tasks
          .filter((t) => t.domain === domain)
          .sort(
            (a, b) =>
              STATUS_ORDER.indexOf(a.status as never) - STATUS_ORDER.indexOf(b.status as never),
          )
        return (
          <section key={domain} className="mb-2 last:mb-0">
            <div className="rounded-t-md border border-b-0 border-white/10 bg-white/[0.04] px-3.5 py-1.5 text-xs font-semibold">
              {domainLabel(domain)} · {stat.total} 实例
              {stat.abnormal > 0 ? `（${stat.total - stat.abnormal} 健康 / ${stat.abnormal} 异常）` : '（全部健康）'}
            </div>
            <Table
              size="small"
              dataSource={items}
              columns={columns}
              rowKey={(record) => `${record.taskType}::${record.source}`}
              pagination={false}
              scroll={{ x: 1200 }}
              expandable={{
                rowExpandable: (record) => !!(record.schedule || record.reasons?.length),
                expandedRowRender: (record) => (
                  <div className="text-xs text-gray-400 space-y-1">
                    {record.schedule && (
                      <div>
                        cron：<code>{record.schedule}</code>
                        {record.isHighFrequency && (
                          <Tag className="ml-2">高频（当日场次 ≥48）</Tag>
                        )}
                        {record.lastRecordsCount != null && (
                          <span className="ml-2">
                            最近入库 {record.lastRecordsCount}
                            {record.lastRecordsDate ? `（${record.lastRecordsDate}）` : ''}
                          </span>
                        )}
                      </div>
                    )}
                    {record.reasons?.map((reason) => (
                      <div key={reason}>· {reason}</div>
                    ))}
                  </div>
                ),
              }}
            />
          </section>
        )
      })}
      {domains.length === 0 && !loading && (
        <Typography.Text type="secondary">暂无快照数据，点击「立即检测」生成</Typography.Text>
      )}
    </div>
  )
}
