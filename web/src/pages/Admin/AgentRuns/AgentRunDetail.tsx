import { ArrowLeftOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Descriptions, Skeleton, Tag, Typography } from 'antd'
import { useNavigate, useParams } from 'react-router-dom'

import { useAdminAgentRunDetail } from '@/hooks/useAdminAgentRuns'
import { formatDateTime } from '@/utils/formatters'

import { RunningStepPlaceholder, StepCard } from './StepPayload'

function kindLabel(kind: string, period: string | null): string {
  if (kind === 'plan') return '每日计划'
  if (period === 'week') return '周度复盘'
  if (period === 'month') return '月度复盘'
  return '日度复盘'
}

function statusTag(status: string) {
  if (status === 'success') return <Tag color="success">成功</Tag>
  if (status === 'failed') return <Tag color="error">失败</Tag>
  if (status === 'running') return <Tag color="processing">执行中</Tag>
  return <Tag color="warning">跳过（缓存命中）</Tag>
}

function formatDuration(ms: number | null): string {
  if (ms == null) return '-'
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`
  return `${ms}ms`
}

/** 会话详情（聊天式时间线）：头部概要 + 步骤卡片纵向时间线。 */
export function AgentRunDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const runId = id ? Number(id) : null
  const detailQuery = useAdminAgentRunDetail(runId)
  const detail = detailQuery.data

  if (detailQuery.isLoading) {
    return (
      <Card variant="borderless">
        <Skeleton active />
      </Card>
    )
  }

  if (!detail) {
    return (
      <Card
        title={
          <Button
            size="small"
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate('/admin/agent-runs')}
          >
            返回会话列表
          </Button>
        }
        variant="borderless"
      >
        <Alert
          message="会话不存在"
          description={detailQuery.error instanceof Error ? detailQuery.error.message : undefined}
          type="error"
          showIcon
        />
      </Card>
    )
  }

  const isRunning = detail.status === 'running'

  return (
    <Card
      title={
        <div className="flex items-center gap-3">
          <Button
            size="small"
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate('/admin/agent-runs')}
          >
            返回
          </Button>
          <span>
            {detail.agentKey} · {kindLabel(detail.kind, detail.period)} ·{' '}
            {detail.tradeDate ?? '-'}
          </span>
          {statusTag(detail.status)}
        </div>
      }
      variant="borderless"
    >
      <Descriptions
        size="small"
        column={{ xs: 1, sm: 2, md: 4 }}
        bordered
        items={[
          { key: 'kind', label: '类型', children: kindLabel(detail.kind, detail.period) },
          { key: 'period', label: '周期', children: detail.period ?? '-' },
          {
            key: 'trigger',
            label: '触发方式',
            children: detail.triggerType === 'manual' ? '手动' : '定时',
          },
          { key: 'tradeDate', label: '基准交易日', children: detail.tradeDate ?? '-' },
          { key: 'status', label: '状态', children: statusTag(detail.status) },
          { key: 'duration', label: '总耗时', children: formatDuration(detail.durationMs) },
          {
            key: 'startedAt',
            label: '开始时间',
            children: formatDateTime(detail.startedAt),
          },
          {
            key: 'finishedAt',
            label: '结束时间',
            children: detail.finishedAt ? formatDateTime(detail.finishedAt) : '-',
          },
          {
            key: 'collectorLogId',
            label: '采集任务日志',
            children:
              detail.collectorLogId != null ? `collector_log #${detail.collectorLogId}` : '-',
          },
        ]}
      />

      {detail.errorMsg && (
        <Alert
          message="执行失败"
          description={<pre className="m-0 whitespace-pre-wrap text-xs">{detail.errorMsg}</pre>}
          type="error"
          showIcon
          className="mt-4"
        />
      )}

      {detail.summary && Object.keys(detail.summary).length > 0 && (
        <div className="mt-4 rounded border border-white/10 bg-white/[0.03] p-3">
          <Typography.Text type="secondary" className="!text-[11px]">
            结果摘要
          </Typography.Text>
          <pre className="m-0 mt-1 overflow-auto whitespace-pre-wrap font-mono text-[11px] text-gray-300">
            {JSON.stringify(detail.summary, null, 2)}
          </pre>
        </div>
      )}

      <Typography.Title level={5} className="!mb-3 !mt-6">
        执行时间线
      </Typography.Title>
      <div className="ml-3 space-y-3 border-l border-white/10 pl-4">
        {detail.steps.map((step) => (
          <div key={step.seq} className="relative">
            <span className="absolute -left-[21px] top-4 h-2 w-2 rounded-full bg-sky-500" />
            <StepCard step={step} />
          </div>
        ))}
        {detail.steps.length === 0 && (
          <Typography.Text type="secondary" className="text-xs">
            暂无步骤记录（会话可能启动即失败）
          </Typography.Text>
        )}
        {isRunning && <RunningStepPlaceholder />}
      </div>
    </Card>
  )
}
