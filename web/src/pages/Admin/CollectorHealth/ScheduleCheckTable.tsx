import { Alert, Card, DatePicker, Table, Tag, Tooltip, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import dayjs, { type Dayjs } from 'dayjs'
import { useState } from 'react'

import { getSourceLabel, getTaskLabel } from '@/utils/collectorTaskLabels'
import type { ApiCollectorScheduleCheckItem } from '@ai-invest/shared'

import { causeLabel, domainLabel, ROLE_META } from './constants'
import { useCollectorHealthScheduleCheck } from '@/hooks/useCollectorHealth'

const WINDOW_COLUMNS = [
  { key: 'success', label: '按期成功', color: '#2ea043' },
  { key: 'skipped', label: '豁免跳过', color: '#8a8f98' },
  { key: 'failed', label: '失败', color: '#f85149' },
  { key: 'missing', label: '应跑未跑', color: '#f85149' },
] as const

export function ScheduleCheckTable() {
  const [day, setDay] = useState<string>(dayjs().format('YYYY-MM-DD'))
  const { data, isLoading } = useCollectorHealthScheduleCheck(day)

  const columns: ColumnsType<ApiCollectorScheduleCheckItem> = [
    {
      title: '任务实例',
      dataIndex: 'taskType',
      key: 'taskType',
      render: (_: string, record: ApiCollectorScheduleCheckItem) => (
        <div>
          <div>{getTaskLabel(record.taskType)}</div>
          <Typography.Text type="secondary" className="text-xs">
            {record.taskType} · {getSourceLabel(record.source)} · {domainLabel(record.domain)}
          </Typography.Text>
        </div>
      ),
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
      title: 'cron',
      dataIndex: 'schedule',
      key: 'schedule',
      width: 130,
      responsive: ['xl'],
      render: (value: string | null) => (value ? <code className="text-xs">{value}</code> : '-'),
    },
    ...WINDOW_COLUMNS.map((col) => ({
      title: col.label,
      key: col.key,
      width: 90,
      align: 'center' as const,
      render: (_: unknown, record: ApiCollectorScheduleCheckItem) => {
        if (record.exempted) return <span className="text-gray-400">-</span>
        const value = record[`${col.key}Windows` as keyof ApiCollectorScheduleCheckItem]
        return (
          <span style={{ color: typeof value === 'number' && value > 0 ? col.color : undefined }}>
            {value}
          </span>
        )
      },
    })),
    {
      title: '豁免',
      dataIndex: 'exempted',
      key: 'exempted',
      width: 70,
      align: 'center' as const,
      render: (exempted: boolean) => (exempted ? <Tag>豁免</Tag> : '-'),
    },
    {
      title: '最近错误',
      dataIndex: 'lastErrorSummary',
      key: 'lastErrorSummary',
      width: 240,
      ellipsis: true,
      render: (_: string | null, record: ApiCollectorScheduleCheckItem) =>
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
  ]

  return (
    <Card
      size="small"
      title={
        <div className="flex items-center gap-3">
          <span>计划核对（应跑 vs 实跑）</span>
          <DatePicker
            value={dayjs(day)}
            allowClear={false}
            disabledDate={(d: Dayjs) => d.isAfter(dayjs(), 'day')}
            onChange={(d) => d && setDay(d.format('YYYY-MM-DD'))}
          />
        </div>
      }
    >
      {data && !data.isTradeDay && (
        <Alert
          message={`${data.date} 非交易日，不产生应跑窗口，全部实例豁免`}
          type="info"
          showIcon
          className="mb-3"
        />
      )}
      <Tooltip title="按运行日志现算，与快照无关；用于核对任意历史日期的计划执行情况">
        <Table
          size="small"
          dataSource={data?.items ?? []}
          columns={columns}
          rowKey={(record) => `${record.taskType}::${record.source}`}
          loading={isLoading}
          pagination={false}
          scroll={{ x: 900 }}
        />
      </Tooltip>
    </Card>
  )
}
