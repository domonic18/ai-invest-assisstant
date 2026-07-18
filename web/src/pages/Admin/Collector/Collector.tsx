import { PlayCircleOutlined, SyncOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Space, Table, Tag, Typography, message } from 'antd'
import { useState } from 'react'

import { useCollectorLogs, useRunCollectorTask } from '@/hooks/useCollectorAdmin'
import type {
  CollectorTaskName,
  CollectorTaskOption,
  CollectorTaskRunOptions,
} from '@ai-invest/shared'

import { CollectorTaskModal } from './CollectorTaskModal'

const TASK_OPTIONS: CollectorTaskOption[] = [
  { key: 'kline', label: 'K 线采集' },
  { key: 'auction', label: '集合竞价采集' },
  { key: 'fund-flow', label: '资金流向采集' },
  { key: 'news', label: '新闻采集' },
  { key: 'company-profile', label: '公司概况采集' },
  { key: 'disclosure', label: '公告披露采集' },
  { key: 'sector-fund-flow', label: '板块资金流向采集' },
  { key: 'dragon-list', label: '龙虎榜采集' },
  { key: 'research-report', label: '个股研报采集' },
  { key: 'financial-report', label: '财报采集' },
  { key: 'ipo-info', label: 'IPO 信息采集' },
  { key: 'fund-holdings', label: '基金持仓采集' },
  { key: 'macro', label: '宏观经济采集' },
  { key: 'stock-list', label: '股票列表同步' },
]

const STATUS_TAG: Record<string, { color: string; label: string }> = {
  success: { color: 'green', label: '成功' },
  partial: { color: 'orange', label: '部分成功' },
  failed: { color: 'red', label: '失败' },
  pending: { color: 'gold', label: '排队中' },
  running: { color: 'processing', label: '运行中' },
  skipped: { color: 'default', label: '跳过' },
}

export function Collector() {
  const { data: logs, isLoading, refetch } = useCollectorLogs(20)
  const runMutation = useRunCollectorTask()

  const [modalOpen, setModalOpen] = useState(false)
  const [selectedTask, setSelectedTask] = useState<CollectorTaskOption | null>(null)

  const handleOpenModal = (task: CollectorTaskOption) => {
    setSelectedTask(task)
    setModalOpen(true)
  }

  const handleRun = async (taskName: CollectorTaskName, options: CollectorTaskRunOptions) => {
    try {
      const body = {
        preferred_source: options.preferredSource || undefined,
        symbols: options.symbols,
        period: options.period || undefined,
        start_date: options.startDate || undefined,
        end_date: options.endDate || undefined,
        sector_type: options.sectorType || undefined,
        indicators: options.indicators,
        report_types: options.reportTypes,
        report_date: options.reportDate || undefined,
      }
      await runMutation.mutateAsync({ taskName, body })
      const label = TASK_OPTIONS.find((t) => t.key === taskName)?.label ?? taskName
      message.info(`「${label}」已派发到采集队列，执行状态见下方日志`)
      setModalOpen(false)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '触发失败')
    }
  }

  const columns = [
    { title: '任务', dataIndex: 'taskName', key: 'taskName' },
    { title: '渠道', dataIndex: 'source', key: 'source', render: (value: string | null) => value ?? '-' },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (value: string) => {
        const tag = STATUS_TAG[value] ?? { color: 'default', label: value }
        return <Tag color={tag.color}>{tag.label}</Tag>
      },
    },
    { title: '入库数', dataIndex: 'recordsCount', key: 'recordsCount' },
    {
      title: '开始时间',
      dataIndex: 'startedAt',
      key: 'startedAt',
      render: (value: string | null) => value ?? '-',
    },
    {
      title: '结束时间',
      dataIndex: 'finishedAt',
      key: 'finishedAt',
      render: (value: string | null) => value ?? '-',
    },
    {
      title: '错误信息',
      dataIndex: 'errorMsg',
      key: 'errorMsg',
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
    <Card
      title="采集任务"
      variant="borderless"
      extra={
        <Space>
          <Button icon={<SyncOutlined />} onClick={() => refetch()} loading={isLoading}>
            刷新日志
          </Button>
        </Space>
      }
    >
      <Alert
        message="点击任务按钮后，会弹出渠道选择与高级选项。系统默认按「支持该任务且已启用」的渠道自动选择，也可手动指定。"
        type="info"
        showIcon
        className="mb-4"
      />

      <Space wrap className="mb-6">
        {TASK_OPTIONS.map((task) => (
          <Button
            key={task.key}
            type="primary"
            icon={<PlayCircleOutlined />}
            onClick={() => handleOpenModal(task)}
            loading={runMutation.isPending}
          >
            {task.label}
          </Button>
        ))}
      </Space>

      <Table
        dataSource={logs || []}
        columns={columns}
        rowKey="id"
        loading={isLoading}
        pagination={false}
      />

      <CollectorTaskModal
        open={modalOpen}
        task={selectedTask}
        onCancel={() => setModalOpen(false)}
        onSubmit={handleRun}
        loading={runMutation.isPending}
      />
    </Card>
  )
}
