import {
  ApiOutlined,
  BarChartOutlined,
  CalendarOutlined,
  CloudServerOutlined,
  FileTextOutlined,
  FileDoneOutlined,
  PieChartOutlined,
  PlayCircleOutlined,
  ReadOutlined,
  RobotOutlined,
  TeamOutlined,
  WeiboOutlined,
} from '@ant-design/icons'
import { Alert, Button, Card, Col, Row, Space, Table, Tag, Typography } from 'antd'
import { Link } from 'react-router-dom'

import { useCollectorLogs } from '@/hooks/useCollectorAdmin'
import { usePendingCount } from '@/hooks/useAdminAccount'
import { useIsNarrowScreen } from '@/hooks/useIsNarrowScreen'
import { formatDateTime } from '@/utils/formatters'
import { getSourceLabel, getTaskLabel } from '@/utils/collectorTaskLabels'
import { statusTagColor } from '@ai-invest/shared'

const ADMIN_LINKS = [
  { title: '用户管理', path: '/admin/users', icon: <TeamOutlined />, color: 'bg-blue-500/10 text-blue-400' },
  { title: '用量看板', path: '/admin/usage-dashboard', icon: <PieChartOutlined />, color: 'bg-violet-500/10 text-violet-400' },
  { title: '股票管理', path: '/admin/stocks', icon: <BarChartOutlined />, color: 'bg-green-500/10 text-green-400' },
  { title: '报告管理', path: '/admin/reports', icon: <FileTextOutlined />, color: 'bg-purple-500/10 text-purple-400' },
  { title: '资讯管理', path: '/admin/news', icon: <ReadOutlined />, color: 'bg-orange-500/10 text-orange-400' },
  { title: '模型配置', path: '/admin/model-configs', icon: <RobotOutlined />, color: 'bg-pink-500/10 text-pink-400' },
  { title: 'MCP 服务', path: '/admin/mcp-servers', icon: <ApiOutlined />, color: 'bg-cyan-500/10 text-cyan-400' },
  { title: '分析结果', path: '/admin/ai-results', icon: <FileDoneOutlined />, color: 'bg-teal-500/10 text-teal-400' },
  { title: '采集管理', path: '/admin/collector', icon: <PlayCircleOutlined />, color: 'bg-indigo-500/10 text-indigo-400' },
  { title: '社媒追踪', path: '/admin/social-tracking', icon: <WeiboOutlined />, color: 'bg-rose-500/10 text-rose-400' },
  { title: '服务状态', path: '/admin/system-status', icon: <CloudServerOutlined />, color: 'bg-emerald-500/10 text-emerald-400' },
  { title: '交易日历', path: '/admin/trade-calendar', icon: <CalendarOutlined />, color: 'bg-amber-500/10 text-amber-400' },
]

export function Admin() {
  const { data: logs, isLoading } = useCollectorLogs({ pageSize: 10 })
  const pendingCount = usePendingCount(true).data ?? 0
  const isNarrow = useIsNarrowScreen()

  const logColumns = [
    { title: '任务', dataIndex: 'taskName', key: 'taskName', render: (v: string) => getTaskLabel(v) },
    { title: '来源', dataIndex: 'source', key: 'source', render: (v: string | null) => getSourceLabel(v) },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (v: string) => <Tag color={statusTagColor(v)}>{v}</Tag>,
    },
    { title: '记录数', dataIndex: 'recordsCount', key: 'recordsCount' },
    { title: '开始时间', dataIndex: 'startedAt', key: 'startedAt', width: 170, render: (v: string | null) => formatDateTime(v) },
    {
      title: '错误',
      dataIndex: 'errorMsg',
      key: 'errorMsg',
      width: 240,
      ellipsis: true,
      render: (v: string | null) => v ? <Typography.Text type="danger" ellipsis={{ tooltip: v }}>{v}</Typography.Text> : '-',
    },
  ]
  // 窄屏只留任务/状态/开始时间：固定宽列会保宽，自适应列被挤成一字一行竖排
  const visibleLogColumns = isNarrow
    ? logColumns.filter((c) => ['taskName', 'status', 'startedAt'].includes(c.key))
    : logColumns

  return (
    <div className="space-y-4 md:space-y-6">
      <Typography.Title level={4} className="!mb-0">后台管理</Typography.Title>

      {pendingCount > 0 && (
        <Alert
          type="warning"
          showIcon
          message={`有 ${pendingCount} 个注册申请待审批`}
          description="新用户在审批通过前无法登录；点击右侧按钮直达待审列表处理。"
          action={
            <Link to="/admin/users?status=pending">
              <Button size="small" type="primary" danger>
                去处理
              </Button>
            </Link>
          }
        />
      )}

      <Row gutter={[12, 12]}>
        {ADMIN_LINKS.map((link) => (
          <Col xs={8} sm={8} md={12} lg={6} key={link.path}>
            <Link to={link.path}>
              <Card
                variant="borderless"
                className="h-full hover:opacity-80 transition-opacity"
                styles={isNarrow ? { body: { padding: '12px 4px' } } : undefined}
              >
                {isNarrow ? (
                  <div className="flex flex-col items-center gap-1.5">
                    <span className={`p-2 rounded-lg text-base ${link.color}`}>{link.icon}</span>
                    <span className="text-xs whitespace-nowrap">{link.title}</span>
                  </div>
                ) : (
                  <Space className="text-lg">
                    <span className={`p-2 rounded ${link.color}`}>{link.icon}</span>
                    <span>{link.title}</span>
                  </Space>
                )}
              </Card>
            </Link>
          </Col>
        ))}
      </Row>

      <Card title="最近采集日志" variant="borderless" extra={<Link to="/admin/collector">查看更多</Link>}>
        <Table
          dataSource={logs?.items ?? []}
          columns={visibleLogColumns}
          rowKey="id"
          loading={isLoading}
          pagination={false}
          size="small"
          scroll={{ x: 'max-content' }}
        />
      </Card>
    </div>
  )
}
