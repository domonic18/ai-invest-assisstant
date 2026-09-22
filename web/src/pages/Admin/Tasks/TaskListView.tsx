/** 任务配置列表视图：树形表格（业务分类为可展开目录行，任务为子行）+ 搜索/分类/状态筛选。 */

import { CompressOutlined, ExpandOutlined, SearchOutlined } from '@ant-design/icons'
import { Button, Input, Popconfirm, Select, Space, Table, Tag, Tooltip, Typography } from 'antd'
import { useMemo, useState } from 'react'

import type { AdminTask, CollectorDataTypeChannel } from '@ai-invest/shared'
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

import { getExpandedGroups, setExpandedGroups } from './taskPrefs'

interface TaskListViewProps {
  tasks: AdminTask[]
  loading: boolean
  /** taskType → 任务备注说明（来自任务目录）。 */
  descByTaskType: Map<string, string>
  /** taskType → 渠道优先级列表（priority 升序，来自数据类型渠道配置）。 */
  channelsByType: Map<string, CollectorDataTypeChannel[]>
  onEdit: (task: AdminTask) => void
  onOpenDetail: (task: AdminTask) => void
}

/** 分类目录行（树形父行）。 */
interface CategoryRow {
  id: string
  isCategory: true
  categoryLabel: string
  categoryColor: string
  count: number
  children: AdminTask[]
}

type TaskTreeRow = CategoryRow | AdminTask

function isCategoryRow(row: TaskTreeRow): row is CategoryRow {
  return 'isCategory' in row
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
  channelsByType,
  onEdit,
  onOpenDetail,
}: TaskListViewProps) {
  const [search, setSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null)
  const [activeFilter, setActiveFilter] = useState<boolean | null>(null)
  const [expandedKeys, setExpandedKeys] = useState<string[] | null>(() => getExpandedGroups())

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

  // 业务分类聚合成目录行，任务为其子行
  const treeData = useMemo(() => {
    const byCategory = new Map<string, AdminTask[]>()
    for (const task of filtered) {
      const cat = taskCategoryOf(task.taskType)
      const arr = byCategory.get(cat)
      if (arr) arr.push(task)
      else byCategory.set(cat, [task])
    }
    const rows: CategoryRow[] = []
    for (const [key, meta] of Object.entries(TASK_CATEGORY_META)) {
      const items = byCategory.get(key)
      if (!items?.length) continue
      rows.push({
        id: `cat:${key}`,
        isCategory: true,
        categoryLabel: meta.label,
        categoryColor: meta.color,
        count: items.length,
        children: items,
      })
    }
    return rows
  }, [filtered])

  const allCategoryKeys = useMemo(() => treeData.map((row) => row.id), [treeData])
  // 搜索时全部展开；无搜索按持久化偏好（默认全展开）
  const effectiveExpanded = keywordExpanded(allCategoryKeys, expandedKeys, search)

  const expandAll = () => {
    setExpandedKeys(allCategoryKeys)
    setExpandedGroups(allCategoryKeys)
  }
  const collapseAll = () => {
    setExpandedKeys([])
    setExpandedGroups([])
  }

  const handleExpandedRowsChange = (keys: readonly React.Key[]) => {
    const next = keys.map(String)
    setExpandedKeys(next)
    setExpandedGroups(next)
  }

  const columns = [
    {
      title: '任务',
      key: 'task',
      render: (_: unknown, record: TaskTreeRow) => {
        if (isCategoryRow(record)) {
          return (
            <div className="flex items-center gap-2">
              <span
                className="h-2 w-2 shrink-0 rounded-full"
                style={{ background: record.categoryColor }}
              />
              <span className="text-sm font-medium">{record.categoryLabel}</span>
              <span className="rounded-full bg-white/[0.06] px-1.5 text-[11px] text-[#8a8f98]">
                {record.count}
              </span>
            </div>
          )
        }
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
              <div
                className="truncate text-[11px] text-[#5c616e]"
                title={record.remark ?? descByTaskType.get(record.taskType)}
              >
                {record.remark ?? descByTaskType.get(record.taskType)}
              </div>
            </div>
          </div>
        )
      },
    },
    {
      title: '渠道',
      key: 'channels',
      width: 180,
      render: (_: unknown, record: TaskTreeRow) => {
        if (isCategoryRow(record)) return null
        const backups = (channelsByType.get(record.taskType) ?? []).filter(
          (ch) => ch.source !== record.source && ch.isEnabled,
        )
        const visible = backups.slice(0, 2)
        return (
          <Tooltip
            title={
              backups.length > 0
                ? `备用顺序：${backups.map((ch) => getSourceLabel(ch.source)).join(' → ')}`
                : undefined
            }
          >
            <span className="flex flex-wrap items-center gap-1">
              <span className="rounded border border-[#58a6ff]/40 bg-[#58a6ff]/10 px-1.5 py-0.5 text-[11px] text-[#79c0ff]">
                {getSourceLabel(record.source)}
              </span>
              {visible.map((ch) => (
                <span
                  key={ch.channelId}
                  className="rounded border border-white/10 px-1.5 py-0.5 text-[11px] text-[#8a8f98]"
                >
                  {getSourceLabel(ch.source)}
                </span>
              ))}
              {backups.length > visible.length && (
                <span className="text-[11px] text-[#8a8f98]">
                  +{backups.length - visible.length}
                </span>
              )}
            </span>
          </Tooltip>
        )
      },
    },
    {
      title: '执行时间',
      dataIndex: 'schedule',
      key: 'schedule',
      width: 190,
      render: (value: string | null, record: TaskTreeRow) => {
        if (isCategoryRow(record) || !value) return <span className="text-[#8a8f98]">-</span>
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
      render: (value: string | null, record: TaskTreeRow) =>
        isCategoryRow(record) ? null : <NextRunsCell schedule={value} />,
    },
    {
      title: '状态',
      dataIndex: 'isActive',
      key: 'isActive',
      width: 80,
      render: (value: boolean, record: TaskTreeRow) =>
        isCategoryRow(record) ? null : value ? <Tag color="green">启用</Tag> : <Tag>禁用</Tag>,
    },
    {
      title: '最近运行',
      key: 'lastRun',
      width: 180,
      render: (_: unknown, record: TaskTreeRow) => {
        if (isCategoryRow(record)) return null
        return record.lastStatus ? (
          <Space size={4}>
            <Tag color={statusTagColor(record.lastStatus)}>{record.lastStatus}</Tag>
            <Typography.Text type="secondary" className="text-xs" ellipsis={{ tooltip: record.lastError ?? undefined }}>
              {record.lastRunAt ? formatDateTime(record.lastRunAt) : '-'}
            </Typography.Text>
          </Space>
        ) : (
          <span className="text-[#8a8f98]">-</span>
        )
      },
    },
    {
      title: '操作',
      key: 'actions',
      width: 250,
      render: (_: unknown, record: TaskTreeRow) => {
        if (isCategoryRow(record)) return null
        return (
          <Space size={4}>
            <Button
              size="small"
              loading={triggerMutation.isPending && triggerMutation.variables === record.id}
              onClick={() => triggerMutation.mutateAsync(record.id).catch(() => undefined)}
            >
              触发
            </Button>
            {record.isActive ? (
              <Button
                size="small"
                loading={pauseMutation.isPending && pauseMutation.variables === record.id}
                onClick={() => pauseMutation.mutateAsync(record.id).catch(() => undefined)}
              >
                暂停
              </Button>
            ) : (
              <Button
                size="small"
                loading={resumeMutation.isPending && resumeMutation.variables === record.id}
                onClick={() => resumeMutation.mutateAsync(record.id).catch(() => undefined)}
              >
                恢复
              </Button>
            )}
            <Button size="small" onClick={() => onEdit(record)}>
              编辑
            </Button>
            <Popconfirm title="确认删除？" onConfirm={() => deleteMutation.mutateAsync(record.id)}>
              <Button size="small" danger loading={deleteMutation.isPending && deleteMutation.variables === record.id}>
                删除
              </Button>
            </Popconfirm>
          </Space>
        )
      },
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
          onChange={(e) => setSearch(e.target.value)}
        />
        <Select
          allowClear
          placeholder="业务分类"
          className="min-w-28"
          options={categoryOptions}
          value={categoryFilter}
          onChange={(value) => {
            setCategoryFilter(value ?? null)
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
          }}
        />
        <span className="ml-auto flex items-center gap-1">
          <Tooltip title="展开所有分类目录">
            <Button
              size="small"
              type="text"
              icon={<ExpandOutlined />}
              aria-label="展开所有分类目录"
              onClick={expandAll}
            />
          </Tooltip>
          <Tooltip title="收起所有分类目录">
            <Button
              size="small"
              type="text"
              icon={<CompressOutlined />}
              aria-label="收起所有分类目录"
              onClick={collapseAll}
            />
          </Tooltip>
          <span className="ml-1 text-xs text-[#8a8f98]">
            {treeData.length} 个分类 · {filtered.length} 个任务
          </span>
        </span>
      </div>

      <Table
        size="small"
        dataSource={treeData}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={false}
        expandable={{
          expandedRowKeys: effectiveExpanded,
          onExpandedRowsChange: handleExpandedRowsChange,
        }}
      />
    </div>
  )
}

/** 搜索态强制全展开；否则用持久化偏好，从未设置过默认全展开。 */
function keywordExpanded(
  allKeys: string[],
  stored: string[] | null,
  search: string,
): string[] {
  if (search.trim()) return allKeys
  return stored ?? allKeys
}
