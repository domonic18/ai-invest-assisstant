import { Alert, Card, DatePicker, Table, Tag, Tooltip, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import dayjs, { type Dayjs } from 'dayjs'
import { useState } from 'react'

import { getSourceLabel, getTaskLabel } from '@/utils/collectorTaskLabels'
import type { ApiCollectorScheduleCheckItem } from '@ai-invest/shared'

import { causeLabel, ROLE_CHIP } from './constants'
import { useCollectorHealthScheduleCheck } from '@/hooks/useCollectorHealth'

const WINDOW_COLUMNS = [
  { key: 'success', label: '成功', full: '按期成功', color: '#2ea043' },
  { key: 'skipped', label: '跳过', full: '豁免跳过', color: '#8a8f98' },
  { key: 'failed', label: '失败', full: '失败', color: '#f85149' },
  { key: 'missing', label: '未跑', full: '应跑未跑', color: '#f85149' },
] as const

export function ScheduleCheckTable() {
  const [day, setDay] = useState<string>(dayjs().format('YYYY-MM-DD'))
  const { data, isLoading } = useCollectorHealthScheduleCheck(day)

  const columns: ColumnsType<ApiCollectorScheduleCheckItem> = [
    {
      title: '任务实例',
      dataIndex: 'taskType',
      key: 'taskType',
      render: (_: string, record: ApiCollectorScheduleCheckItem) => {
        const role = ROLE_CHIP[record.role]
        return (
          <div className="whitespace-nowrap">
            <div>{getTaskLabel(record.taskType)}</div>
            <Typography.Text type="secondary" className="text-xs">
              {record.taskType} · {getSourceLabel(record.source)}
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
      title: 'cron',
      dataIndex: 'schedule',
      key: 'schedule',
      width: 110,
      responsive: ['xl'],
      render: (value: string | null) => (value ? <code className="text-xs">{value}</code> : '-'),
    },
    ...WINDOW_COLUMNS.map((col) => ({
      title: (
        <Tooltip title={col.full}>
          <span>{col.label}</span>
        </Tooltip>
      ),
      key: col.key,
      width: 64,
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
      width: 56,
      align: 'center' as const,
      render: (exempted: boolean) => (exempted ? <Tag>豁免</Tag> : '-'),
    },
    {
      title: '最近错误',
      dataIndex: 'lastErrorSummary',
      key: 'lastErrorSummary',
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
          <span>计划核对 · {day}</span>
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
        />
      </Tooltip>
    </Card>
  )
}
