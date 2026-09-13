import { ClearOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Popconfirm, Select, Space, Tag, Typography, message } from 'antd'
import dayjs from 'dayjs'
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { useRunCollectorTask } from '@/hooks/useCollectorAdmin'
import {
  useClearHealthSnapshots,
  useCollectorHealthChannels,
  useCollectorHealthOverview,
  useCollectorHealthTasks,
  useRunHealthCheck,
} from '@/hooks/useCollectorHealth'
import { getTaskLabel } from '@/utils/collectorTaskLabels'
import { formatDateTime } from '@/utils/formatters'

import { ChannelHealthCards } from './ChannelHealthCards'
import { DOMAIN_OPTIONS, STATUS_META, STATUS_ORDER, causeLabel } from './constants'
import { OverviewCards } from './OverviewCards'
import { ScheduleCheckTable } from './ScheduleCheckTable'
import { TaskHealthTable } from './TaskHealthTable'

/** 采集健康 Tab：只读快照 + 立即检测/清空；筛选与 ?domain=&status= 同步。 */
export function CollectorHealth() {
  const [searchParams, setSearchParams] = useSearchParams()
  const domain = searchParams.get('domain')
  const status = searchParams.get('status')

  const { data: overview, isLoading: overviewLoading } = useCollectorHealthOverview()
  const { data: tasks, isLoading: tasksLoading } = useCollectorHealthTasks({ domain, status })
  const { data: channels, isLoading: channelsLoading } = useCollectorHealthChannels()
  const runCheckMutation = useRunHealthCheck()
  const clearMutation = useClearHealthSnapshots()
  const runTaskMutation = useRunCollectorTask()

  const [causeFilter, setCauseFilter] = useState<string | null>(null)
  const [rerunningTaskType, setRerunningTaskType] = useState<string | null>(null)

  const isStale = overview?.staleAfter ? dayjs().isAfter(dayjs(overview.staleAfter)) : false
  const faultCount = overview ? overview.counts.critical + overview.counts.silent : 0

  const setFilter = (key: 'domain' | 'status', value: string | null) => {
    const next = new URLSearchParams(searchParams)
    if (value) next.set(key, value)
    else next.delete(key)
    setSearchParams(next, { replace: true })
  }

  const gotoTab = (params: Record<string, string>) => {
    setSearchParams(params, { replace: true })
  }

  const handleRunCheck = async () => {
    try {
      const result = await runCheckMutation.mutateAsync()
      const faults = (result.statusCounts.critical ?? 0) + (result.statusCounts.silent ?? 0)
      message.success(
        `检测完成：${result.total} 个实例${faults > 0 ? `，${faults} 个故障/静默` : '，全部正常'}`,
      )
    } catch (err) {
      message.error(err instanceof Error ? err.message : '检测失败')
    }
  }

  const handleClear = async () => {
    try {
      const result = await clearMutation.mutateAsync()
      message.info(`已清空 ${result.deleted} 行快照，可点「立即检测」重建`)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '清空失败')
    }
  }

  const handleRerun = async (taskType: string) => {
    setRerunningTaskType(taskType)
    try {
      await runTaskMutation.mutateAsync({ taskName: taskType })
      message.info(`「${getTaskLabel(taskType)}」已派发到采集队列，检测结果将在下轮检测更新`)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '触发失败')
    } finally {
      setRerunningTaskType(null)
    }
  }

  const filteredTasks =
    tasks && causeFilter
      ? tasks.filter((task) => task.lastErrorCause === causeFilter)
      : tasks

  return (
    <div className="space-y-4">
      <Card size="small">
        <div className="flex flex-wrap items-center gap-3">
          <Typography.Text>
            最近检测：
            {overview?.checkedAt ? (
              <span className="font-medium">{formatDateTime(overview.checkedAt)}</span>
            ) : (
              <Tag color="warning">尚未检测</Tag>
            )}
          </Typography.Text>
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            loading={runCheckMutation.isPending}
            onClick={handleRunCheck}
          >
            立即检测
          </Button>
          <Popconfirm
            title="清空全部健康快照？"
            description="下个检测点或「立即检测」会重建全量快照"
            okText="清空"
            cancelText="取消"
            okButtonProps={{ danger: true }}
            onConfirm={handleClear}
          >
            <Button
              icon={<ClearOutlined />}
              loading={clearMutation.isPending}
              disabled={!overview?.checkedAt}
            >
              清空快照
            </Button>
          </Popconfirm>
          <Typography.Text type="secondary" className="text-xs">
            检测由定时任务每日盘前自动执行，页面展示的是快照
          </Typography.Text>
        </div>
      </Card>

      {isStale && overview?.checkedAt && (
        <Alert
          message="检测延迟"
          description={`最近检测于 ${formatDateTime(overview.checkedAt)}，已超过预期检测时限（检测间隔 × 2），检测定时任务可能失联，请检查采集任务配置。`}
          type="warning"
          showIcon
        />
      )}

      {faultCount > 0 && (
        <Alert
          message={`发现 ${faultCount} 个异常实例：${overview?.counts.critical ?? 0} 个故障、${overview?.counts.silent ?? 0} 个静默，请查看下方明细`}
          type="error"
          showIcon
        />
      )}

      {overview && <OverviewCards overview={overview} />}

      <Card
        size="small"
        title="任务实例明细"
        extra={
          <Space>
            <Select
              allowClear
              placeholder="数据域"
              style={{ width: 120 }}
              options={DOMAIN_OPTIONS}
              value={domain ?? null}
              onChange={(value) => setFilter('domain', value)}
            />
            <Select
              allowClear
              placeholder="状态"
              style={{ width: 120 }}
              options={STATUS_ORDER.map((s) => ({ value: s, label: STATUS_META[s].label }))}
              value={status ?? null}
              onChange={(value) => setFilter('status', value)}
            />
            {causeFilter && (
              <Tag closable onClose={() => setCauseFilter(null)} color="red">
                归因：{causeLabel(causeFilter)}
              </Tag>
            )}
          </Space>
        }
      >
        <TaskHealthTable
          tasks={filteredTasks ?? []}
          loading={tasksLoading || overviewLoading}
          rerunningTaskType={rerunningTaskType}
          onViewLogs={(taskType, source) => gotoTab({ tab: 'run', taskName: taskType, source })}
          onRerun={handleRerun}
          onGotoChannels={() => gotoTab({ tab: 'channels' })}
        />
      </Card>

      <ScheduleCheckTable />

      <ChannelHealthCards
        channels={channels ?? []}
        loading={channelsLoading}
        activeCause={causeFilter}
        onCauseClick={(cause) => setCauseFilter((prev) => (prev === cause ? null : cause))}
      />
    </div>
  )
}
