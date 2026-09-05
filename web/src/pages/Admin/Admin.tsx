import {
  BarChartOutlined,
  ContainerOutlined,
  FileTextOutlined,
  FileDoneOutlined,
  PlayCircleOutlined,
  ReadOutlined,
  RobotOutlined,
  SettingOutlined,
  TeamOutlined,
  VerticalAlignTopOutlined,
} from '@ant-design/icons'
import { Card, Col, Row, Space, Table, Tag, Typography } from 'antd'
import { Link } from 'react-router-dom'

import { useCollectorLogs } from '@/hooks/useCollectorAdmin'
import { formatDateTime } from '@/utils/formatters'
import { getSourceLabel, getTaskLabel } from '@/utils/collectorTaskLabels'

const ADMIN_LINKS = [
  { title: '用户管理', path: '/admin/users', icon: <TeamOutlined />, color: 'bg-blue-500/10 text-blue-400' },
  { title: '股票管理', path: '/admin/stocks', icon: <BarChartOutlined />, color: 'bg-green-500/10 text-green-400' },
  { title: '研报管理', path: '/admin/reports', icon: <FileTextOutlined />, color: 'bg-purple-500/10 text-purple-400' },
  { title: '资讯管理', path: '/admin/news', icon: <ReadOutlined />, color: 'bg-orange-500/10 text-orange-400' },
  { title: '任务管理', path: '/admin/tasks', icon: <ContainerOutlined />, color: 'bg-cyan-500/10 text-cyan-400' },
  { title: 'LLM 配置', path: '/admin/llm-configs', icon: <RobotOutlined />, color: 'bg-pink-500/10 text-pink-400' },
  { title: 'AI 结果管理', path: '/admin/ai-results', icon: <FileDoneOutlined />, color: 'bg-teal-500/10 text-teal-400' },
  { title: '跟踪指数', path: '/admin/tracked-indexes', icon: <VerticalAlignTopOutlined />, color: 'bg-amber-500/10 text-amber-400' },
  { title: '采集渠道', path: '/admin/collector-channels', icon: <SettingOutlined />, color: 'bg-gray-500/10 text-gray-400' },
  { title: '采集任务', path: '/admin/collector', icon: <PlayCircleOutlined />, color: 'bg-indigo-500/10 text-indigo-400' },
]

const STATUS_COLORS: Record<string, string> = {
  success: 'green',
  failed: 'red',
  pending: 'gold',
  running: 'blue',
  partial: 'orange',
  skipped: 'default',
}

export function Admin() {
  const { data: logs, isLoading } = useCollectorLogs(10)

  const logColumns = [
    { title: '任务', dataIndex: 'taskName', key: 'taskName', render: (v: string) => getTaskLabel(v) },
    { title: '来源', dataIndex: 'source', key: 'source', render: (v: string | null) => getSourceLabel(v) },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (v: string) => <Tag color={STATUS_COLORS[v] || 'default'}>{v}</Tag>,
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

  return (
    <div className="space-y-6">
      <Typography.Title level={4} className="!mb-0">后台管理</Typography.Title>

      <Row gutter={[16, 16]}>
        {ADMIN_LINKS.map((link) => (
          <Col xs={24} sm={12} lg={6} key={link.path}>
            <Link to={link.path}>
              <Card
                variant="borderless"
                className="h-full hover:opacity-80 transition-opacity"
              >
                <Space className="text-lg">
                  <span className={`p-2 rounded ${link.color}`}>{link.icon}</span>
                  <span>{link.title}</span>
                </Space>
              </Card>
            </Link>
          </Col>
        ))}
      </Row>

      <Card title="最近采集日志" variant="borderless" extra={<Link to="/admin/collector">查看更多</Link>}>
        <Table
          dataSource={logs || []}
          columns={logColumns}
          rowKey="id"
          loading={isLoading}
          pagination={false}
          size="small"
        />
      </Card>
    </div>
  )
}
