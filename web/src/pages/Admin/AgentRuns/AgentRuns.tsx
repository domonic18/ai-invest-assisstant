import { EyeOutlined } from '@ant-design/icons'
import {
  Alert,
  Button,
  Card,
  DatePicker,
  Segmented,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import dayjs, { type Dayjs } from 'dayjs'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { PAGE_SIZE, type ApiAgentRun } from '@ai-invest/shared'

import { useAdminAgentRuns } from '@/hooks/useAdminAgentRuns'
import { useAgentOverview } from '@/hooks/useTradingAgent'
import { DATE_FORMAT, formatDateTime } from '@/utils/formatters'

const KIND_OPTIONS = [
  { value: 'plan', label: '每日计划' },
  { value: 'review', label: '分层复盘' },
]

const PERIOD_OPTIONS = [
  { value: 'day', label: '日' },
  { value: 'week', label: '周' },
  { value: 'month', label: '月' },
]

const STATUS_OPTIONS = [
  { value: 'success', label: '成功' },
  { value: 'failed', label: '失败' },
  { value: 'skipped', label: '跳过（缓存命中）' },
  { value: 'running', label: '执行中' },
]

const TRIGGER_OPTIONS = [
  { value: 'scheduled', label: '定时' },
  { value: 'manual', label: '手动' },
]

function statusTag(status: string) {
  if (status === 'success') return <Tag color="success">成功</Tag>
  if (status === 'failed') return <Tag color="error">失败</Tag>
  if (status === 'running') return <Tag color="processing">执行中</Tag>
  return <Tag color="warning">跳过</Tag>
}

function kindLabel(kind: string, period: string | null) {
  const base = kind === 'plan' ? '每日计划' : '分层复盘'
  if (kind === 'review' && period && period !== 'day') {
    return period === 'week' ? '周度复盘' : '月度复盘'
  }
  return base
}

/** 摘要要点（summary 内键为 snake_case：JSONB 字典值不走 camelCase 转换）。 */
function summaryText(summary: Record<string, unknown> | null): string {
  if (!summary) return '-'
  const parts: string[] = []
  if (summary.cache_hit === true) parts.push('缓存命中')
  if (summary.kb_used === true) parts.push('KB 方法论')
  if (typeof summary.selections === 'number') parts.push(`选股 ${summary.selections}`)
  if (typeof summary.plans === 'number') parts.push(`计划 ${summary.plans}`)
  if (typeof summary.trades === 'number') parts.push(`委托 ${summary.trades}`)
  if (typeof summary.experiences === 'number') parts.push(`经验 ${summary.experiences}`)
  if (Array.isArray(summary.dropped_codes) && summary.dropped_codes.length > 0) {
    parts.push(`剔除 ${summary.dropped_codes.length}`)
  }
  return parts.join(' · ') || '-'
}

function formatDuration(ms: number | null): string {
  if (ms == null) return '-'
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`
  return `${ms}ms`
}

export function AgentRuns() {
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(PAGE_SIZE.table)
  const [agentKey, setAgentKey] = useState<string | undefined>(undefined)
  const [kind, setKind] = useState<string | undefined>(undefined)
  const [period, setPeriod] = useState<string | undefined>(undefined)
  const [status, setStatus] = useState<string | undefined>(undefined)
  const [triggerType, setTriggerType] = useState<string | undefined>(undefined)
  const [dateRange, setDateRange] = useState<[string | null, string | null]>([null, null])

  const agentsQuery = useAgentOverview()
  const agentOptions = useMemo(
    () =>
      (agentsQuery.data?.items ?? []).map((item) => ({
        value: item.profile.agentKey,
        label: `${item.profile.name}（${item.profile.agentKey}）`,
      })),
    [agentsQuery.data],
  )

  const listQuery = useAdminAgentRuns(
    {
      page,
      pageSize,
      agentKey,
      kind,
      period,
      status,
      triggerType,
      tradeDateStart: dateRange[0] ?? undefined,
      tradeDateEnd: dateRange[1] ?? undefined,
    },
    // 存在执行中会话时 5s 轮询（范本 useCollectorHealth）
    { refetchInterval: 5000 },
  )

  const columns: ColumnsType<ApiAgentRun> = [
    { title: 'Agent', dataIndex: 'agentKey', key: 'agentKey', width: 110 },
    {
      title: '类型',
      key: 'kind',
      width: 110,
      render: (_, record) => (
        <Tag color={record.kind === 'plan' ? 'geekblue' : 'purple'}>
          {kindLabel(record.kind, record.period)}
        </Tag>
      ),
    },
    {
      title: '触发',
      dataIndex: 'triggerType',
      key: 'triggerType',
      width: 80,
      render: (value: string) => (value === 'manual' ? '手动' : '定时'),
    },
    { title: '基准日', dataIndex: 'tradeDate', key: 'tradeDate', width: 110 },
    { title: '状态', dataIndex: 'status', key: 'status', width: 90, render: statusTag },
    {
      title: '总耗时',
      dataIndex: 'durationMs',
      key: 'durationMs',
      width: 90,
      render: (value: number | null) => formatDuration(value),
    },
    {
      title: '摘要',
      key: 'summary',
      render: (_, record) => (
        <span className="text-xs text-gray-400">{summaryText(record.summary)}</span>
      ),
    },
    {
      title: '开始时间',
      dataIndex: 'startedAt',
      key: 'startedAt',
      width: 170,
      render: (value: string) => formatDateTime(value),
    },
    {
      title: '操作',
      key: 'actions',
      width: 90,
      render: (_, record) => (
        <Button
          size="small"
          icon={<EyeOutlined />}
          onClick={() => navigate(`/admin/agent-runs/${record.id}`)}
        >
          详情
        </Button>
      ),
    },
  ]

  const handleRangeChange = (dates: [Dayjs | null, Dayjs | null] | null) => {
    setDateRange(
      dates
        ? [dates[0]?.format(DATE_FORMAT) ?? null, dates[1]?.format(DATE_FORMAT) ?? null]
        : [null, null],
    )
    setPage(1)
  }

  return (
    <Card title="会话管理" variant="borderless">
      <Typography.Paragraph type="secondary" className="!mb-3">
        交易 Agent 自动化任务（每日计划 / 分层复盘）执行轨迹：每次生成一条会话，
        详情可查看输入组装、知识库检索、LLM 全文与校验落库全过程。
      </Typography.Paragraph>
      <Space className="mb-4" wrap>
        <Select
          value={agentKey}
          options={agentOptions}
          allowClear
          showSearch
          optionFilterProp="label"
          placeholder="全部 Agent"
          style={{ width: 220 }}
          loading={agentsQuery.isLoading}
          onChange={(value) => {
            setAgentKey(value)
            setPage(1)
          }}
        />
        <Segmented
          value={kind ?? 'all'}
          options={[
            { value: 'all', label: '全部' },
            ...KIND_OPTIONS,
          ]}
          onChange={(value) => {
            setKind(value === 'all' ? undefined : String(value))
            setPage(1)
          }}
        />
        <Select
          value={period}
          options={PERIOD_OPTIONS}
          allowClear
          placeholder="全部周期"
          style={{ width: 110 }}
          onChange={(value) => {
            setPeriod(value)
            setPage(1)
          }}
        />
        <Select
          value={status}
          options={STATUS_OPTIONS}
          allowClear
          placeholder="全部状态"
          style={{ width: 160 }}
          onChange={(value) => {
            setStatus(value)
            setPage(1)
          }}
        />
        <Select
          value={triggerType}
          options={TRIGGER_OPTIONS}
          allowClear
          placeholder="全部触发"
          style={{ width: 120 }}
          onChange={(value) => {
            setTriggerType(value)
            setPage(1)
          }}
        />
        <DatePicker.RangePicker
          value={
            dateRange[0] && dateRange[1]
              ? ([dayjs(dateRange[0]), dayjs(dateRange[1])] as [Dayjs, Dayjs])
              : null
          }
          onChange={handleRangeChange}
          allowEmpty={[true, true]}
        />
      </Space>
      {listQuery.error && (
        <Alert
          message="加载失败"
          description={listQuery.error instanceof Error ? listQuery.error.message : '未知错误'}
          type="error"
          showIcon
          className="mb-4"
        />
      )}
      <Table
        dataSource={listQuery.data?.items ?? []}
        columns={columns}
        rowKey="id"
        loading={listQuery.isLoading}
        scroll={{ x: 'max-content' }}
        pagination={{
          current: page,
          pageSize,
          total: listQuery.data?.total ?? 0,
          showSizeChanger: true,
          showTotal: (total) => `共 ${total} 条会话`,
          onChange: (p, ps) => {
            setPage(p)
            setPageSize(ps)
          },
        }}
      />
    </Card>
  )
}
