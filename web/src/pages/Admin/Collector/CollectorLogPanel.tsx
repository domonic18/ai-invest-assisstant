/** 执行页右栏：今日汇总 chips + 日期/状态/任务筛选 + 日志表分页（运行中 3s 自动轮询）。 */

import { ReloadOutlined } from '@ant-design/icons'
import { Button, DatePicker, Select, Space, Spin, Table, Tag, Typography } from 'antd'
import dayjs, { type Dayjs } from 'dayjs'
import { useState } from 'react'

import { statusLabel, statusTagColor } from '@ai-invest/shared'
import type { CollectorLog, CollectorTaskOption } from '@ai-invest/shared'

import { useCollectorLogSummary, useCollectorLogs } from '@/hooks/useCollectorAdmin'
import { getSourceLabel, getTaskLabel } from '@/utils/collectorTaskLabels'
import { formatDateTime } from '@/utils/formatters'

const PAGE_SIZE = 20

const STATUS_OPTIONS = [
  { value: 'success', label: '成功' },
  { value: 'partial', label: '部分成功' },
  { value: 'failed', label: '失败' },
  { value: 'skipped', label: '跳过' },
  { value: 'running', label: '运行中' },
  { value: 'pending', label: '排队中' },
]

const IN_FLIGHT = new Set(['running', 'pending'])

const { RangePicker } = DatePicker

const DATE_PRESETS = [
  { label: '今天', value: [dayjs(), dayjs()] as [Dayjs, Dayjs] },
  { label: '近 7 天', value: [dayjs().subtract(6, 'day'), dayjs()] as [Dayjs, Dayjs] },
  { label: '近 30 天', value: [dayjs().subtract(29, 'day'), dayjs()] as [Dayjs, Dayjs] },
]

interface CollectorLogPanelProps {
  taskNameFilter: string | null
  sourceFilter: string | null
  taskOptions: CollectorTaskOption[]
  onFilterChange: (patch: { taskName?: string | null; source?: string | null }) => void
}

function SummaryChips() {
  const { data } = useCollectorLogSummary()
  if (!data) return null
  return (
    <Space wrap size={4}>
      <span className="text-xs text-[#8a8f98]">今日</span>
      <Tag color="success">✔ {data.successCount + data.partialCount}</Tag>
      <Tag color="error">✕ {data.failedCount}</Tag>
      <Tag color="processing">⏳ {data.runningCount + data.pendingCount}</Tag>
      <Tag>⏭ {data.skippedCount}</Tag>
    </Space>
  )
}

function formatDuration(startedAt: string | null, finishedAt: string | null): string {
  if (!startedAt || !finishedAt) return '-'
  const seconds = dayjs(finishedAt).diff(dayjs(startedAt), 'second')
  return seconds >= 0 ? `${seconds}s` : '-'
}

export function CollectorLogPanel({
  taskNameFilter,
  sourceFilter,
  taskOptions,
  onFilterChange,
}: CollectorLogPanelProps) {
  const [status, setStatus] = useState<string | null>(null)
  const [dateRange, setDateRange] = useState<[Dayjs, Dayjs] | null>(null)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(PAGE_SIZE)

  const { data, isLoading, isFetching, refetch } = useCollectorLogs({
    page,
    pageSize,
    taskName: taskNameFilter,
    source: sourceFilter,
    status,
    startDate: dateRange?.[0]?.format('YYYY-MM-DD') ?? null,
    endDate: dateRange?.[1]?.format('YYYY-MM-DD') ?? null,
  })
  const logs = data?.items ?? []
  const hasInFlight = logs.some((log) => IN_FLIGHT.has(log.status))

  const columns = [
    {
      title: '任务',
      dataIndex: 'taskName',
      key: 'taskName',
      render: (value: string) => <span className="font-medium">{getTaskLabel(value)}</span>,
    },
    { title: '渠道', dataIndex: 'source', key: 'source', render: (v: string | null) => getSourceLabel(v) },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (value: string) => <Tag color={statusTagColor(value)}>{statusLabel(value)}</Tag>,
    },
    { title: '入库数', dataIndex: 'recordsCount', key: 'recordsCount', width: 70 },
    {
      title: '耗时',
      key: 'duration',
      width: 70,
      render: (_: unknown, record: CollectorLog) => formatDuration(record.startedAt, record.finishedAt),
    },
    {
      title: '开始',
      dataIndex: 'startedAt',
      key: 'startedAt',
      width: 150,
      render: (value: string | null) => (value ? formatDateTime(value) : '-'),
    },
    {
      title: '结束',
      dataIndex: 'finishedAt',
      key: 'finishedAt',
      width: 150,
      render: (value: string | null) => (value ? formatDateTime(value) : '-'),
    },
    {
      title: '错误',
      dataIndex: 'errorMsg',
      key: 'errorMsg',
      ellipsis: true,
      render: (value: string | null) =>
        value ? (
          <Typography.Text type="danger" ellipsis={{ tooltip: value }}>
            {value}
          </Typography.Text>
        ) : (
          '-'
        ),
    },
  ]

  return (
    <div className="flex flex-col gap-3">
      <SummaryChips />

      <div className="flex flex-wrap items-center gap-2">
        <RangePicker
          allowClear
          presets={DATE_PRESETS}
          value={dateRange}
          onChange={(value) => {
            setDateRange(value as [Dayjs, Dayjs] | null)
            setPage(1)
          }}
        />
        <Select
          allowClear
          placeholder="状态"
          className="min-w-24"
          value={status}
          options={STATUS_OPTIONS}
          onChange={(value) => {
            setStatus(value ?? null)
            setPage(1)
          }}
        />
        <Select
          allowClear
          showSearch
          optionFilterProp="label"
          placeholder="任务"
          className="min-w-40"
          value={taskNameFilter}
          options={taskOptions}
          onChange={(value) => {
            onFilterChange({ taskName: value ?? null })
            setPage(1)
          }}
        />
        {sourceFilter && (
          <Tag closable onClose={() => onFilterChange({ source: null })}>
            {getSourceLabel(sourceFilter)}
          </Tag>
        )}
        <Button
          size="small"
          icon={<ReloadOutlined />}
          onClick={() => refetch()}
          loading={isFetching}
        />
        {hasInFlight && (
          <span className="flex items-center gap-1.5 text-xs text-[#8a8f98]">
            <Spin size="small" />
            运行中任务每 3 秒自动刷新
          </span>
        )}
      </div>

      <Table
        size="small"
        dataSource={logs}
        columns={columns}
        rowKey="id"
        loading={isLoading}
        pagination={{
          current: page,
          pageSize,
          total: data?.total ?? 0,
          showSizeChanger: true,
          showTotal: (total) => `共 ${total} 条`,
          onChange: (nextPage, nextSize) => {
            setPage(nextSize !== pageSize ? 1 : nextPage)
            setPageSize(nextSize)
          },
        }}
      />
    </div>
  )
}
