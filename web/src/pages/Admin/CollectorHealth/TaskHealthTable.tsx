import { PlayCircleOutlined } from '@ant-design/icons'
import { Button, Table, Tag, Tooltip, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import { getSourceLabel, getTaskLabel } from '@/utils/collectorTaskLabels'
import { formatDateTime } from '@/utils/formatters'
import type { ApiCollectorHealthTaskItem } from '@ai-invest/shared'

import { causeLabel, domainLabel, rateText, ROLE_META, STATUS_META } from './constants'

interface TaskHealthTableProps {
  tasks: ApiCollectorHealthTaskItem[]
  loading?: boolean
  rerunningTaskType: string | null
  onViewLogs: (taskType: string, source: string) => void
  onRerun: (taskType: string) => void
  onGotoChannels: () => void
}

const RATE_RENDER = (value: number | null) =>
  value == null ? (
    '-'
  ) : (
    <span style={{ color: value < 0.8 ? '#f85149' : value < 0.9 ? '#d29922' : undefined }}>
      {rateText(value)}
    </span>
  )

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
      render: (_, record) => (
        <div>
          <div>{getTaskLabel(record.taskType)}</div>
          <Typography.Text type="secondary" className="text-xs">
            {record.taskType} · {getSourceLabel(record.source)} · {domainLabel(record.domain)}
          </Typography.Text>
        </div>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 110,
      render: (_, record) => {
        const meta = STATUS_META[record.status]
        return (
          <Tooltip title={record.reasons?.length ? record.reasons.join('；') : undefined}>
            <Tag color={meta.color}>{meta.label}</Tag>
          </Tooltip>
        )
      },
    },
    {
      title: '角色',
      dataIndex: 'role',
      key: 'role',
      width: 90,
      render: (role: string) => {
        const meta = ROLE_META[role]
        return meta ? <Tag color={meta.color}>{meta.label}</Tag> : role
      },
    },
    {
      title: '24h 成功率',
      dataIndex: 'successRate24h',
      key: 'successRate24h',
      width: 110,
      responsive: ['lg'],
      render: RATE_RENDER,
    },
    {
      title: '7d 成功率',
      dataIndex: 'successRate7d',
      key: 'successRate7d',
      width: 100,
      responsive: ['lg'],
      render: RATE_RENDER,
    },
    {
      title: '连败',
      dataIndex: 'consecutiveFailures',
      key: 'consecutiveFailures',
      width: 70,
      render: (value: number) => (value > 0 ? <span style={{ color: '#f85149' }}>{value}</span> : 0),
    },
    {
      title: '缺口窗口',
      dataIndex: 'windowsWithoutSuccess',
      key: 'windowsWithoutSuccess',
      width: 90,
      render: (value: number) => (value > 0 ? <span style={{ color: '#d29922' }}>{value}</span> : 0),
    },
    {
      title: '最近成功',
      dataIndex: 'lastSuccessAt',
      key: 'lastSuccessAt',
      width: 150,
      responsive: ['xl'],
      render: (value: string | null) => (value ? formatDateTime(value) : '-'),
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
      width: 150,
      fixed: 'right',
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

  return (
    <Table
      size="small"
      dataSource={tasks}
      columns={columns}
      rowKey={(record) => `${record.taskType}::${record.source}`}
      loading={loading}
      pagination={false}
      scroll={{ x: 1100 }}
      expandable={{
        rowExpandable: (record) => !!(record.schedule || record.reasons?.length),
        expandedRowRender: (record) => (
          <div className="text-xs text-gray-500 space-y-1">
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
  )
}
