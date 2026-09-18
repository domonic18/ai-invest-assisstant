/** 任务详情抽屉：任务信息 / cron 释义 / 未来执行 / 最近运行 / 操作。 */

import { Button, Descriptions, Drawer, Popconfirm, Space, Table, Tag, Typography } from 'antd'
import dayjs from 'dayjs'

import type { AdminTask, CollectorDataTypeChannel } from '@ai-invest/shared'
import { statusLabel, statusTagColor } from '@ai-invest/shared'

import { useCollectorLogs } from '@/hooks/useCollectorAdmin'
import {
  usePauseAdminTask,
  useResumeAdminTask,
  useTriggerAdminTask,
} from '@/hooks/useAdminTasks'
import { getSourceLabel, getTaskLabel } from '@/utils/collectorTaskLabels'
import { cronZh, formatNextRunLabel, nextRuns } from '@/utils/cron'
import { formatCronExpression, formatDateTime } from '@/utils/formatters'

interface TaskDetailDrawerProps {
  task: AdminTask | null
  /** 任务备注（来自任务目录 TASK_SPECS.description）。 */
  description?: string
  /** taskType → 渠道优先级列表（priority 升序，来自数据类型渠道配置）。 */
  channelsByType: Map<string, CollectorDataTypeChannel[]>
  onClose: () => void
  onEdit: (task: AdminTask) => void
  onDelete: (id: number) => void
}

function ScheduleSection({ schedule }: { schedule: string | null }) {
  if (!schedule) {
    return <Typography.Text type="secondary">未配置（不参与定时调度）</Typography.Text>
  }
  const runs = nextRuns(schedule, 5)
  return (
    <div className="flex flex-col gap-2 text-sm">
      <div>
        <span className="text-[#8a8f98]">紧凑释义：</span>
        {cronZh(schedule) ?? formatCronExpression(schedule)}
      </div>
      <div>
        <span className="text-[#8a8f98]">完整释义：</span>
        {formatCronExpression(schedule)}
      </div>
      <div className="font-mono text-xs text-[#8a8f98]">{schedule}</div>
      <div>
        <span className="text-[#8a8f98]">未来 5 次执行：</span>
        {runs && runs.length > 0 ? (
          <ul className="m-0 list-none p-0">
            {runs.map((t) => (
              <li key={t.valueOf()}>{formatNextRunLabel(t)}（{t.format('YYYY-MM-DD HH:mm')}）</li>
            ))}
          </ul>
        ) : (
          '-'
        )}
      </div>
    </div>
  )
}

export function TaskDetailDrawer({
  task,
  description,
  channelsByType,
  onClose,
  onEdit,
  onDelete,
}: TaskDetailDrawerProps) {
  const triggerMutation = useTriggerAdminTask()
  const pauseMutation = usePauseAdminTask()
  const resumeMutation = useResumeAdminTask()

  // collector_log.task_name 存 TASK_SPECS 键（taskType），非 collector_task 实例名
  const { data: recentRuns } = useCollectorLogs({
    pageSize: 3,
    taskName: task?.taskType ?? null,
  })

  return (
    <Drawer
      title={task ? getTaskLabel(task.taskType) : '任务详情'}
      width={520}
      open={task != null}
      onClose={onClose}
      footer={
        task && (
          <Space className="justify-end w-full">
            <Button
              type="primary"
              loading={triggerMutation.isPending}
              onClick={() => triggerMutation.mutateAsync(task.id).catch(() => undefined)}
            >
              触发
            </Button>
            {task.isActive ? (
              <Button
                loading={pauseMutation.isPending}
                onClick={() => pauseMutation.mutateAsync(task.id).catch(() => undefined)}
              >
                暂停
              </Button>
            ) : (
              <Button
                loading={resumeMutation.isPending}
                onClick={() => resumeMutation.mutateAsync(task.id).catch(() => undefined)}
              >
                恢复
              </Button>
            )}
            <Button onClick={() => onEdit(task)}>编辑</Button>
            <Popconfirm title="确认删除？" onConfirm={() => onDelete(task.id)}>
              <Button danger>删除</Button>
            </Popconfirm>
          </Space>
        )
      }
    >
      {task && (
        <div className="flex flex-col gap-5">
          <Descriptions column={1} size="small" bordered>
            <Descriptions.Item label="任务名称">
              <span className="font-mono text-xs">{task.taskName}</span>
            </Descriptions.Item>
            <Descriptions.Item label="任务类型">{getTaskLabel(task.taskType)}</Descriptions.Item>
            {description && (
              <Descriptions.Item label="备注">{description}</Descriptions.Item>
            )}
            <Descriptions.Item label="渠道">
              {getSourceLabel(task.source)}
              {(channelsByType.get(task.taskType) ?? [])
                .filter((ch) => ch.source !== task.source)
                .map((ch, index) => (
                  <div key={ch.channelId} className="mt-0.5 text-xs text-[#8a8f98]">
                    备{index + 1} · {getSourceLabel(ch.source)}
                    {!ch.isEnabled && '（禁用）'}
                  </div>
                ))}
            </Descriptions.Item>
            <Descriptions.Item label="状态">
              {task.isActive ? <Tag color="green">启用</Tag> : <Tag>禁用</Tag>}
            </Descriptions.Item>
            <Descriptions.Item label="最近运行">
              {task.lastStatus ? (
                <Space size={4}>
                  <Tag color={statusTagColor(task.lastStatus)}>{statusLabel(task.lastStatus)}</Tag>
                  {task.lastRunAt ? formatDateTime(task.lastRunAt) : '-'}
                </Space>
              ) : (
                '-'
              )}
            </Descriptions.Item>
            {task.lastError && (
              <Descriptions.Item label="最近错误">
                <Typography.Text type="danger" className="text-xs">
                  {task.lastError}
                </Typography.Text>
              </Descriptions.Item>
            )}
            <Descriptions.Item label="更新时间">
              {task.updatedAt ? dayjs(task.updatedAt).format('YYYY-MM-DD HH:mm') : '-'}
            </Descriptions.Item>
          </Descriptions>

          <div>
            <div className="mb-2 text-sm font-medium">调度配置</div>
            <ScheduleSection schedule={task.schedule} />
          </div>

          <div>
            <div className="mb-2 text-sm font-medium">最近运行</div>
            <Table
              size="small"
              dataSource={recentRuns?.items ?? []}
              rowKey="id"
              pagination={false}
              columns={[
                {
                  title: '状态',
                  dataIndex: 'status',
                  render: (value: string) => (
                    <Tag color={statusTagColor(value)}>{statusLabel(value)}</Tag>
                  ),
                },
                {
                  title: '入库数',
                  dataIndex: 'recordsCount',
                  width: 70,
                },
                {
                  title: '开始时间',
                  dataIndex: 'startedAt',
                  render: (value: string | null) => (value ? formatDateTime(value) : '-'),
                },
              ]}
            />
          </div>
        </div>
      )}
    </Drawer>
  )
}
