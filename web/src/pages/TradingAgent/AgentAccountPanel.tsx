/**
 * Agent 专属模拟盘账户面板（D31）：配置页只呈现本 Agent 的绑定关系——
 * 未绑定时「绑定账户」弹对话框从全平台未占用账户中选择；已绑定展示账户
 * 关键信息 + 解绑。全平台账户列表/启停/排错仍在系统管理页，此处不重复。
 */
import { LinkOutlined } from '@ant-design/icons'
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Empty,
  Modal,
  Popconfirm,
  Select,
  Skeleton,
  Tag,
  Tooltip,
  Typography,
} from 'antd'
import { useMemo, useState } from 'react'

import {
  useAdminPaperTradeAccounts,
  useClearPaperTradeAgent,
  useDesignatePaperTradeAgent,
} from '@/hooks/usePaperTrade'
import { formatDateTime } from '@/utils/formatters'

import { useAgentKey } from './agentKeyContext'

export function AgentAccountPanel() {
  const agentKey = useAgentKey()
  const { data, isLoading } = useAdminPaperTradeAccounts()
  const designate = useDesignatePaperTradeAgent()
  const clear = useClearPaperTradeAgent()
  const [bindOpen, setBindOpen] = useState(false)
  const [selectedId, setSelectedId] = useState<number | undefined>(undefined)

  const bound = data?.items.find((account) => account.agentKey === agentKey) ?? null
  const available = useMemo(
    () => (data?.items ?? []).filter((account) => account.agentKey == null),
    [data],
  )

  const openBind = () => {
    setSelectedId(available[0]?.id)
    setBindOpen(true)
  }

  const confirmBind = () => {
    if (selectedId == null) return
    designate.mutate(
      { accountId: selectedId, agentKey },
      { onSuccess: () => setBindOpen(false) },
    )
  }

  return (
    <Card
      size="small"
      title="模拟盘账户"
      extra={
        bound ? (
          <Popconfirm
            title={`解绑「${bound.name}」？`}
            description="解绑后该 Agent 暂无关联账户，不执行盘中/盘后交易；账户本体保留，可随时重新绑定。"
            okText="解绑"
            okButtonProps={{ danger: true }}
            cancelText="返回"
            onConfirm={() => clear.mutate({ accountId: bound.id, agentKey })}
          >
            <Button size="small" danger loading={clear.isPending}>
              解绑账户
            </Button>
          </Popconfirm>
        ) : (
          <Button
            size="small"
            type="primary"
            icon={<LinkOutlined />}
            onClick={openBind}
            disabled={isLoading}
          >
            绑定账户
          </Button>
        )
      }
    >
      {isLoading ? (
        <Skeleton active title={false} paragraph={{ rows: 3 }} />
      ) : bound ? (
        <Descriptions
          size="small"
          column={2}
          items={[
            {
              key: 'name',
              label: '账户名称',
              children: (
                <span>
                  {bound.name}
                  {!bound.isEnabled && <Tag className="ml-2">已停用</Tag>}
                </span>
              ),
            },
            { key: 'counter', label: '柜台账户 ID', children: bound.counterAccountId },
            { key: 'token', label: 'Token', children: bound.tokenMasked },
            {
              key: 'synced',
              label: '最近同步',
              children: bound.lastSyncedAt ? (
                formatDateTime(bound.lastSyncedAt)
              ) : (
                <Typography.Text type="secondary">未同步</Typography.Text>
              ),
            },
            {
              key: 'error',
              label: '最近错误',
              span: 2,
              children: bound.lastError ? (
                <Tooltip title={bound.lastError}>
                  <Typography.Text type="danger" ellipsis>
                    {bound.lastError}
                  </Typography.Text>
                </Tooltip>
              ) : (
                '-'
              ),
            },
          ]}
        />
      ) : (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="未绑定模拟盘账户（绑定后才会实际下单与盘后同步）"
        >
          <Typography.Text type="secondary" className="text-xs">
            全平台账户管理见「系统管理 → 模拟盘账户」
          </Typography.Text>
        </Empty>
      )}

      <Modal
        title="绑定模拟盘账户"
        open={bindOpen}
        onOk={confirmBind}
        onCancel={() => setBindOpen(false)}
        okText="绑定"
        okButtonProps={{ disabled: selectedId == null, loading: designate.isPending }}
        cancelText="取消"
        destroyOnClose
      >
        <Alert
          type="info"
          showIcon
          className="!mb-3"
          message="agent 专属账户全局唯一：绑定时该账户若曾归属其他 Agent 将自动还原为普通账户；专属账户禁止人工下单。"
        />
        {available.length === 0 ? (
          <Typography.Text type="secondary" className="text-xs">
            暂无可绑定的账户（均已被其他 Agent 占用或尚未创建）；可先在「模拟盘」页「账户管理」添加账户。
          </Typography.Text>
        ) : (
          <Select
            className="w-full"
            placeholder="选择未占用的模拟盘账户"
            value={selectedId}
            onChange={setSelectedId}
            options={available.map((account) => ({
              value: account.id,
              label: `${account.name}（${account.counterAccountId}）`,
            }))}
          />
        )}
      </Modal>
    </Card>
  )
}
