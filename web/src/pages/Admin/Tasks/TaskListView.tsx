/** 任务配置列表视图：紧凑 cron 释义 + 下次执行预览 + 搜索/业务分类/状态筛选。 */

import { SearchOutlined } from '@ant-design/icons'
import { Button, Input, Popconfirm, Select, Space, Table, Tag, Tooltip, Typography } from 'antd'
import { useMemo, useState } from 'react'

import type { AdminTask } from '@ai-invest/shared'
import { statusTagColor } from '@ai-invest/shared'

import {
  useDeleteAdminTask,
  usePauseAdminTask,
  useResumeAdminTask,
  useTriggerAdminTask,
} from '@/hooks/useAdminTasks'
import { getSourceLabel, getTaskLabel } from '@/utils/collectorTaskLabels'
import { cronZh, formatNextRunLabel, nextRuns } from '@/utils/cron'
import {
  TASK_CATEGORY_META,
  taskCategoryColor,
  taskCategoryLabel,
  taskCategoryOf,
} from '@/utils/taskCategoryMeta'
import { formatCronExpression, formatDateTime } from '@/utils/formatters'

interface TaskListViewProps {
  tasks: AdminTask[]
  loading: boolean
  /** taskType → 任务备注说明（来自任务目录）。 */
  descByTaskType: Map<string, string>
  onEdit: (task: AdminTask) => void
  onOpenDetail: (task: AdminTask) => void
}

function NextRunsCell({ schedule }: { schedule: string | null }) {
  if (!schedule) return <span className="text-[#8a8f98]">-</span>
  const runs = nextRuns(schedule, 3)
  if (!runs || runs.length === 0) return '-'
  return (
    <span className="text-xs">
      {runs.map((t) => formatNextRunLabel(t)).join(' · ')}
    </span>
  )
}

export function TaskListView({
  tasks,
  loading,
  descByTaskType,
  onEdit,
  onOpenDetail,
}: TaskListViewProps) {
  const [search, setSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null)
  const [activeFilter, setActiveFilter] = useState<boolean | null>(null)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  const triggerMutation = useTriggerAdminTask()
  const pauseMutation = usePauseAdminTask()
  const resumeMutation = useResumeAdminTask()
  const deleteMutation = useDeleteAdminTask()

  const categoryOptions = useMemo(
    () =>
      Object.entries(TASK_CATEGORY_META).map(([value, meta]) => ({
        value,
        label: meta.label,
      })),
    [],
  )

  const filtered = useMemo(() => {
    const keyword = search.trim().toLowerCase()
    return tasks.filter((task) => {
      if (keyword) {
        const haystack = [
          getTaskLabel(task.taskType),
          task.taskName,
          task.taskType,
          getSourceLabel(task.source),
        ]
          .join('\n')
          .toLowerCase()
        if (!haystack.includes(keyword)) return false
      }
      if (categoryFilter && taskCategoryOf(task.taskType) !== categoryFilter) {
        return false
      }
      if (activeFilter !== null && task.isActive !== activeFilter) return false
      return true
    })
  }, [tasks, search, categoryFilter, activeFilter])

  const columns = [
    {
      title: '任务',
      key: 'task',
      render: (_: unknown, record: AdminTask) => {
        const cat = taskCategoryOf(record.taskType)
        return (
          <div className="flex items-center gap-2">
            {cat !== 'other' && (
              <span
                className="h-2 w-2 shrink-0 rounded-full"
                style={{ background: taskCategoryColor(cat) }}
                title={taskCategoryLabel(cat)}
              />
            )}
            <div className="min-w-0">
              <a onClick={() => onOpenDetail(record)} className="text-sm">
                {getTaskLabel(record.taskType)}
              </a>
              <div className="font-mono text-[11px] text-[#8a8f98]">{record.taskName}</div>
              <div className="truncate text-[11px] text-[#5c616e]" title={descByTaskType.get(record.taskType)}>
                {descByTaskType.get(record.taskType)}
              </div>
            </div>
          </div>
        )
      },
    },
    {
      title: '渠道',
      dataIndex: 'source',
      key: 'source',
      width: 110,
      render: (value: string | null) => getSourceLabel(value),
    },
    {
      title: '执行时间',
      dataIndex: 'schedule',
      key: 'schedule',
      width: 190,
      render: (value: string | null, record: AdminTask) => {
        if (!value) return <span className="text-[#8a8f98]">-</span>
        const compact = cronZh(value)
        return (
          <Tooltip
            title={
              <div className="text-xs">
                <div>{formatCronExpression(value)}</div>
                <div className="font-mono opacity-70">{value}</div>
              </div>
            }
          >
            <span className={record.isActive ? '' : 'opacity-50'}>
              {compact ?? formatCronExpression(value)}
            </span>
          </Tooltip>
        )
      },
    },
    {
      title: '下次执行',
      dataIndex: 'schedule',
      key: 'nextRuns',
      width: 200,
      render: (value: string | null) => <NextRunsCell schedule={value} />,
    },
    {
      title: '状态',
      dataIndex: 'isActive',
      key: 'isActive',
      width: 80,
      render: (value: boolean) =>
        value ? <Tag color="green">启用</Tag> : <Tag>禁用</Tag>,
    },
    {
      title: '最近运行',
      key: 'lastRun',
      width: 180,
      render: (_: unknown, record: AdminTask) =>
        record.lastStatus ? (
          <Space size={4}>
            <Tag color={statusTagColor(record.lastStatus)}>{record.lastStatus}</Tag>
            <Typography.Text type="secondary" className="text-xs" ellipsis={{ tooltip: record.lastError ?? undefined }}>
              {record.lastRunAt ? formatDateTime(record.lastRunAt) : '-'}
            </Typography.Text>
          </Space>
        ) : (
          <span className="text-[#8a8f98]">-</span>
        ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 250,
      render: (_: unknown, record: AdminTask) => (
        <Space size={4}>
          <Button
            size="small"
            loading={triggerMutation.isPending}
            onClick={() => triggerMutation.mutateAsync(record.id).catch(() => undefined)}
          >
            触发
          </Button>
          {record.isActive ? (
            <Button
              size="small"
              loading={pauseMutation.isPending}
              onClick={() => pauseMutation.mutateAsync(record.id).catch(() => undefined)}
            >
              暂停
            </Button>
          ) : (
            <Button
              size="small"
              loading={resumeMutation.isPending}
              onClick={() => resumeMutation.mutateAsync(record.id).catch(() => undefined)}
            >
              恢复
            </Button>
          )}
          <Button size="small" onClick={() => onEdit(record)}>
            编辑
          </Button>
          <Popconfirm title="确认删除？" onConfirm={() => deleteMutation.mutateAsync(record.id)}>
            <Button size="small" danger>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Input
          allowClear
          prefix={<SearchOutlined className="text-[#8a8f98]" />}
          placeholder="搜索任务 / 渠道"
          className="w-56"
          onChange={(e) => {
            setSearch(e.target.value)
            setPage(1)
          }}
        />
        <Select
          allowClear
          placeholder="业务分类"
          className="min-w-28"
          options={categoryOptions}
          value={categoryFilter}
          onChange={(value) => {
            setCategoryFilter(value ?? null)
            setPage(1)
          }}
        />
        <Select
          allowClear
          placeholder="状态"
          className="min-w-24"
          value={activeFilter}
          options={[
            { value: true, label: '启用' },
            { value: false, label: '禁用' },
          ]}
          onChange={(value) => {
            setActiveFilter(value ?? null)
            setPage(1)
          }}
        />
        <span className="ml-auto text-xs text-[#8a8f98]">共 {filtered.length} 条</span>
      </div>

      <Table
        size="small"
        dataSource={filtered}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={{
          current: page,
          pageSize,
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
