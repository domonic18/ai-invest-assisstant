import { DownOutlined } from '@ant-design/icons'
import { Card, Col, Row, Segmented, Statistic, Table, Tag, Typography } from 'antd'
import type { TableColumnsType } from 'antd'
import dayjs from 'dayjs'
import ReactECharts from 'echarts-for-react'
import { useState } from 'react'
import {
  USAGE_FEATURE_LABELS,
  type ApiUsagePerUser,
  type UsageFeature,
} from '@ai-invest/shared'

import { useAccountSettings, useUsageDashboard, useUsagePerUsers } from '@/hooks/useAdminAccount'

const DAY_OPTIONS = [
  { label: '近 7 天', value: 7 },
  { label: '近 30 天', value: 30 },
  { label: '近 90 天', value: 90 },
]

function Sparkline({ daily }: { daily: ApiUsagePerUser['daily'] }) {
  const max = Math.max(1, ...daily.map((point) => point.totalTokens))
  return (
    <div className="flex items-end gap-[2px] h-6" title="日消耗趋势">
      {daily.slice(-30).map((point) => (
        <div
          key={point.date}
          className="w-[5px] rounded-sm bg-[#5e6ad2]"
          style={{ height: `${Math.max(8, (point.totalTokens / max) * 100)}%`, opacity: point.totalTokens ? 1 : 0.15 }}
        />
      ))}
    </div>
  )
}

export function UsageDashboard() {
  const [days, setDays] = useState(30)
  const dashboardQ = useUsageDashboard(days)
  const perUsersQ = useUsagePerUsers(days)
  const settingsQ = useAccountSettings()
  const data = dashboardQ.data
  const perUsers = perUsersQ.data ?? []

  const trendOption = {
    backgroundColor: 'transparent',
    grid: { left: 56, right: 16, top: 24, bottom: 28 },
    tooltip: { trigger: 'axis' as const },
    xAxis: {
      type: 'category' as const,
      data: data?.trendDaily.map((point) => point.date) ?? [],
      axisLabel: { color: '#8a8f98', fontSize: 10 },
      axisLine: { lineStyle: { color: '#23262d' } },
    },
    yAxis: {
      type: 'value' as const,
      axisLabel: { color: '#8a8f98', fontSize: 10 },
      splitLine: { lineStyle: { color: '#1c1f26' } },
    },
    series: [
      {
        type: 'bar' as const,
        data: data?.trendDaily.map((point) => point.totalTokens) ?? [],
        itemStyle: { color: '#5e6ad2', borderRadius: [2, 2, 0, 0] },
        barMaxWidth: 18,
      },
    ],
  }

  const totalTokens = data?.trendDaily.reduce((sum, p) => sum + p.totalTokens, 0) ?? 0
  const perUserTotal = perUsers.reduce((sum, user) => sum + user.totalTokens, 0)

  const userColumns: TableColumnsType<ApiUsagePerUser> = [
    {
      title: '成员',
      dataIndex: 'username',
      width: 140,
      render: (value: string | null, record) => value ?? `#${record.userId}`,
    },
    {
      title: `近 ${days} 天消耗`,
      dataIndex: 'totalTokens',
      width: 130,
      align: 'right',
      sorter: (a, b) => a.totalTokens - b.totalTokens,
      render: (value: number) => <span className="font-mono">{value.toLocaleString('zh-CN')}</span>,
    },
    {
      title: '占比',
      key: 'share',
      width: 120,
      render: (_: unknown, record) => {
        const share = perUserTotal ? (record.totalTokens / perUserTotal) * 100 : 0
        return (
          <div className="flex items-center gap-2">
            <div className="flex-1 h-1.5 rounded bg-[#181a21] overflow-hidden min-w-[48px]">
              <div className="h-full rounded bg-[#5e6ad2]" style={{ width: `${share}%` }} />
            </div>
            <span className="font-mono text-xs text-[#8a8f98] w-10 text-right">
              {share.toFixed(1)}%
            </span>
          </div>
        )
      },
    },
    {
      title: '调用次数',
      dataIndex: 'calls',
      width: 90,
      align: 'right',
      render: (value: number) => <span className="font-mono">{value.toLocaleString('zh-CN')}</span>,
    },
    {
      title: '日趋势',
      key: 'trend',
      width: 160,
      render: (_: unknown, record) => <Sparkline daily={record.daily} />,
    },
    {
      title: '最近使用',
      dataIndex: 'lastUsedAt',
      width: 140,
      render: (value: string | null) =>
        value ? dayjs(value).format('MM-DD HH:mm') : '-',
    },
  ]

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <Typography.Title level={4} className="!mb-0">
            用量看板
          </Typography.Title>
          <Typography.Paragraph type="secondary" className="!mt-1 !mb-0 text-xs">
            全站 token 消耗趋势与成员明细（按北京时间聚合）；系统任务与自备 Key 调用计入统计但不占个人配额
          </Typography.Paragraph>
        </div>
        <Segmented options={DAY_OPTIONS} value={days} onChange={(v) => setDays(v as number)} />
      </div>

      <Row gutter={[12, 12]}>
        <Col xs={12} md={6}>
          <Card variant="borderless" loading={dashboardQ.isLoading}>
            <Statistic title={`近 ${days} 天消耗（tokens）`} value={totalTokens} />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card variant="borderless" loading={dashboardQ.isLoading}>
            <Statistic
              title="估算占比（estimated）"
              value={data ? (data.estimatedRatio * 100).toFixed(1) : 0}
              suffix="%"
            />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card variant="borderless" loading={dashboardQ.isLoading}>
            <Statistic title="配额耗尽用户" value={data?.exhaustedUsers ?? 0} />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card variant="borderless" loading={settingsQ.isLoading}>
            <Statistic
              title="全局默认配额"
              value={settingsQ.data?.defaultQuotaTokens ?? 0}
              suffix={
                settingsQ.data?.adminExempt ? (
                  <Tag bordered={false} color="purple" className="!ml-2">
                    管理员豁免
                  </Tag>
                ) : null
              }
            />
          </Card>
        </Col>
      </Row>

      <Card variant="borderless" title="日消耗趋势" loading={dashboardQ.isLoading}>
        <ReactECharts
          option={trendOption}
          notMerge
          lazyUpdate
          style={{ height: 260 }}
          theme="dark"
        />
      </Card>

      <Row gutter={[12, 12]}>
        <Col xs={24} lg={12}>
          <Card variant="borderless" title="按功能分布" loading={dashboardQ.isLoading}>
            <DistributionRows
              entries={Object.entries(data?.byFeature ?? {}).map(([key, value]) => [
                USAGE_FEATURE_LABELS[key as UsageFeature] ?? key,
                value,
              ])}
            />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card variant="borderless" title="按模型分布" loading={dashboardQ.isLoading}>
            <DistributionRows entries={Object.entries(data?.byModel ?? {})} mono />
          </Card>
        </Col>
      </Row>

      <Card
        variant="borderless"
        title="成员消耗明细"
        extra={<span className="text-xs text-[#5c616e]">展开行查看每日明细</span>}
        loading={perUsersQ.isLoading}
      >
        {perUsers.length === 0 && !perUsersQ.isLoading ? (
          <Typography.Text type="secondary" className="text-xs">
            近 {days} 天暂无成员消耗记录
          </Typography.Text>
        ) : (
          <Table
            size="small"
            rowKey={(row) => String(row.userId)}
            dataSource={perUsers}
            columns={userColumns}
            pagination={perUsers.length > 15 ? { pageSize: 15 } : false}
            expandable={{
              expandedRowRender: (record) => <UserDailyDetail daily={record.daily} />,
              expandIcon: ({ expanded, onExpand, record }) => (
                <DownOutlined
                  className="text-[10px] text-[#8a8f98]"
                  style={{ transform: expanded ? 'rotate(180deg)' : undefined, cursor: 'pointer' }}
                  onClick={(e) => onExpand(record, e)}
                />
              ),
            }}
          />
        )}
      </Card>
    </div>
  )
}

function UserDailyDetail({ daily }: { daily: ApiUsagePerUser['daily'] }) {
  const max = Math.max(1, ...daily.map((point) => point.totalTokens))
  return (
    <div className="pl-2 space-y-1.5">
      {daily
        .slice()
        .reverse()
        .map((point) => (
          <div key={point.date} className="flex items-center gap-3 text-xs">
            <span className="w-20 font-mono text-[#8a8f98]">{point.date}</span>
            <div className="flex-1 h-1.5 rounded bg-[#181a21] overflow-hidden">
              <div
                className="h-full rounded bg-[#5e6ad2]"
                style={{ width: `${(point.totalTokens / max) * 100}%` }}
              />
            </div>
            <span className="font-mono text-[#8a8f98] w-24 text-right">
              {point.totalTokens.toLocaleString('zh-CN')} tokens
            </span>
          </div>
        ))}
    </div>
  )
}

function DistributionRows({
  entries,
  mono,
}: {
  entries: [string, number][]
  mono?: boolean
}) {
  const total = entries.reduce((sum, [, value]) => sum + value, 0)
  if (!entries.length) {
    return <Typography.Text type="secondary" className="text-xs">暂无数据</Typography.Text>
  }
  return (
    <div className="space-y-2">
      {entries
        .sort((a, b) => b[1] - a[1])
        .map(([label, value]) => (
          <div key={label} className="flex items-center gap-3 text-xs">
            <span className={`w-32 truncate text-[#8a8f98] ${mono ? 'font-mono' : ''}`}>
              {label}
            </span>
            <div className="flex-1 h-1.5 rounded bg-[#181a21] overflow-hidden">
              <div
                className="h-full rounded bg-[#5e6ad2]"
                style={{ width: `${total ? (value / total) * 100 : 0}%` }}
              />
            </div>
            <span className="font-mono text-[#8a8f98] w-24 text-right">
              {value.toLocaleString('zh-CN')}
            </span>
          </div>
        ))}
    </div>
  )
}
