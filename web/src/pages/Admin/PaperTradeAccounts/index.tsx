import { RobotOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Popconfirm, Space, Switch, Table, Tag, Tooltip, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import type { ApiPaperTradeAdminAccount } from '@ai-invest/shared'

import {
  useAdminPaperTradeAccounts,
  useDesignatePaperTradeAgent,
  useSetPaperTradeAccountEnabled,
} from '@/hooks/usePaperTrade'
import { formatDateTime } from '@/utils/formatters'

/** 管理端模拟盘账户：全平台列表 + 启停 + 指定 agent 专属账户（全局唯一）。 */
export function PaperTradeAccountsAdmin() {
  const accountsQuery = useAdminPaperTradeAccounts()
  const designateMutation = useDesignatePaperTradeAgent()
  const enabledMutation = useSetPaperTradeAccountEnabled()

  const columns: ColumnsType<ApiPaperTradeAdminAccount> = [
    {
      title: '名称',
      dataIndex: 'name',
      width: 140,
      render: (name: string, record) => (
        <Space size={4}>
          {name}
          {record.isAgent && <Tag color="gold">Agent</Tag>}
          {!record.isEnabled && <Tag>已停用</Tag>}
        </Space>
      ),
    },
    { title: '归属用户', dataIndex: 'userId', width: 90 },
    { title: '柜台账户 ID', dataIndex: 'counterAccountId', width: 160 },
    { title: 'Token', dataIndex: 'tokenMasked', width: 140, ellipsis: true },
    {
      title: '最近同步',
      dataIndex: 'lastSyncedAt',
      width: 160,
      render: (v: string | null | undefined) =>
        v ? formatDateTime(v) : <Typography.Text type="secondary">未同步</Typography.Text>,
    },
    {
      title: '最近错误',
      dataIndex: 'lastError',
      ellipsis: true,
      render: (v: string | null | undefined) =>
        v ? (
          <Tooltip title={v}>
            <Typography.Text type="danger" ellipsis>
              {v}
            </Typography.Text>
          </Tooltip>
        ) : (
          '-'
        ),
    },
    {
      title: '启用',
      dataIndex: 'isEnabled',
      width: 80,
      render: (v: boolean, record) => (
        <Switch
          checked={v}
          loading={enabledMutation.isPending && enabledMutation.variables?.accountId === record.id}
          onChange={(checked) =>
            void enabledMutation
              .mutateAsync({ accountId: record.id, enabled: checked })
              .catch(() => {})
          }
        />
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 150,
      render: (_, record) =>
        record.isAgent ? (
          <Typography.Text type="secondary">当前 agent 账户</Typography.Text>
        ) : (
          <Popconfirm
            title="指定为 agent 专属账户？"
            description="全局唯一，原 agent 账户自动还原为普通账户。"
            onConfirm={() => void designateMutation.mutateAsync(record.id).catch(() => {})}
          >
            <Button
              size="small"
              icon={<RobotOutlined />}
              loading={
                designateMutation.isPending && designateMutation.variables === record.id
              }
            >
              指定为 Agent
            </Button>
          </Popconfirm>
        ),
    },
  ]

  return (
    <Card title="模拟交易账户" variant="borderless">
      <Typography.Paragraph type="secondary" className="mb-4">
        全平台模拟盘账户管理：agent 专属账户全局唯一（用于后续 agent 自动交易），停用账户跳过盘后同步且禁止人工交易。
      </Typography.Paragraph>
      {accountsQuery.error && (
        <Alert
          message="加载失败"
          description={
            accountsQuery.error instanceof Error ? accountsQuery.error.message : '未知错误'
          }
          type="error"
          showIcon
          className="mb-4"
        />
      )}
      <Table<ApiPaperTradeAdminAccount>
        rowKey="id"
        columns={columns}
        dataSource={accountsQuery.data?.items ?? []}
        loading={accountsQuery.isLoading}
        pagination={false}
        locale={{ emptyText: '暂无账户配置' }}
        scroll={{ x: 1000 }}
      />
    </Card>
  )
}
