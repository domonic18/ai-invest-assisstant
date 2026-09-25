import { DeleteOutlined, EditOutlined, PlusOutlined } from '@ant-design/icons'
import {
  Alert,
  Button,
  Form,
  Input,
  Modal,
  Popconfirm,
  Space,
  Table,
  Tag,
  Tooltip,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useState } from 'react'

import type { ApiPaperTradeAccount } from '@ai-invest/shared'

import {
  useDeletePaperTradeAccount,
  usePaperTradeAccounts,
  useSavePaperTradeAccount,
} from '@/hooks/usePaperTrade'
import { fallColor, formatDateTime } from '@/utils/formatters'

interface AccountFormValues {
  name: string
  token: string
  counterAccountId: string
}

type ModalView = { kind: 'list' } | { kind: 'form'; account: ApiPaperTradeAccount | null }

/** 账户配置弹窗：列表 ⇄ 表单两态。添加/编辑先进入表单，确认后回到列表（token 掩码展示）。 */
export function AccountManagerModal({
  open,
  onClose,
}: {
  open: boolean
  onClose: () => void
}) {
  const [form] = Form.useForm<AccountFormValues>()
  const [view, setView] = useState<ModalView>({ kind: 'list' })
  const accountsQuery = usePaperTradeAccounts()
  const saveMutation = useSavePaperTradeAccount()
  const deleteMutation = useDeletePaperTradeAccount()

  const editing = view.kind === 'form' ? view.account : null

  const openCreate = () => {
    form.resetFields()
    setView({ kind: 'form', account: null })
  }

  const openEdit = (account: ApiPaperTradeAccount) => {
    form.setFieldsValue({
      name: account.name,
      token: '',
      counterAccountId: account.counterAccountId,
    })
    setView({ kind: 'form', account })
  }

  const backToList = () => {
    form.resetFields()
    setView({ kind: 'list' })
  }

  const columns: ColumnsType<ApiPaperTradeAccount> = [
    {
      title: '名称',
      dataIndex: 'name',
      width: 120,
      render: (name: string, record) => (
        <Space size={4}>
          {name}
          {record.isAgent && <Tag color="gold">Agent</Tag>}
          {!record.isEnabled && <Tag>已停用</Tag>}
        </Space>
      ),
    },
    { title: '柜台账户 ID', dataIndex: 'counterAccountId', width: 150, ellipsis: true },
    { title: 'Token', dataIndex: 'tokenMasked', width: 120, ellipsis: true },
    {
      title: '最近同步',
      dataIndex: 'lastSyncedAt',
      width: 140,
      render: (v: string | null | undefined) =>
        v ? formatDateTime(v) : <Typography.Text type="secondary">未同步</Typography.Text>,
    },
    {
      title: '最近错误',
      dataIndex: 'lastError',
      width: 230,
      ellipsis: { showTitle: false },
      render: (v: string | null | undefined) =>
        v ? (
          <Tooltip title={v} placement="topLeft">
            <Typography.Text style={{ color: fallColor() }} className="text-xs">
              {v}
            </Typography.Text>
          </Tooltip>
        ) : (
          <Typography.Text type="secondary">-</Typography.Text>
        ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 110,
      fixed: 'right' as const,
      render: (_, record) => (
        <Space size={4}>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => openEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="删除后不可恢复，确认删除？"
            onConfirm={() => deleteMutation.mutate(record.id)}
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  const handleSubmit = async (values: AccountFormValues) => {
    try {
      await saveMutation.mutateAsync({
        accountId: editing?.id,
        data: values,
      })
      backToList()
    } catch {
      // 错误提示由 axios 拦截器统一弹出（409 冲突等）
    }
  }

  return (
    <Modal
      title="模拟交易账户管理"
      open={open}
      onCancel={onClose}
      footer={null}
      width={980}
      destroyOnHidden
    >
      {view.kind === 'list' ? (
        <div className="space-y-3 pt-2">
          <Alert
            type="info"
            showIcon
            message={
              <span className="text-xs">
                首次使用：在掘金客户端「交易」→「账户管理」添加仿真账户，将其 token
                与账户 ID 录入系统（
                <Typography.Link
                  href="https://www.myquant.cn/docs2/operatingInstruction/trading/%E4%BB%BF%E7%9C%9F%E4%BA%A4%E6%98%93.html"
                  target="_blank"
                >
                  官方教程
                </Typography.Link>
                ）。token 视同密码仅保存加密副本；柜台账户全平台唯一，最多 10 个。
              </span>
            }
          />
          <div className="flex justify-end">
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
              添加账户
            </Button>
          </div>
          <Table<ApiPaperTradeAccount>
            size="small"
            rowKey="id"
            columns={columns}
            dataSource={accountsQuery.data?.items ?? []}
            loading={accountsQuery.isLoading}
            pagination={false}
            scroll={{ x: 860 }}
            locale={{ emptyText: '暂无账户，点击右上角「添加账户」录入' }}
          />
        </div>
      ) : (
        <div className="space-y-3 pt-2">
          <Typography.Title level={5} className="mb-0!">
            {editing ? `编辑：${editing.name}` : '添加账户'}
          </Typography.Title>
          <Form<AccountFormValues>
            form={form}
            layout="vertical"
            onFinish={(values) => void handleSubmit(values)}
            className="max-w-xl"
            requiredMark={false}
          >
            <Form.Item
              name="name"
              label="展示名"
              rules={[{ required: true, message: '请输入名称' }]}
            >
              <Input placeholder="如：人工盘" maxLength={64} />
            </Form.Item>
            <Form.Item
              name="counterAccountId"
              label="柜台账户 ID"
              rules={[{ required: true, message: '请输入账户 ID' }]}
            >
              <Input placeholder="掘金仿真 account_id" maxLength={64} />
            </Form.Item>
            <Form.Item
              name="token"
              label={editing ? '新 Token（留空不变）' : 'Token'}
              rules={editing ? [] : [{ required: true, message: '请输入 token' }]}
              extra={
                <Typography.Text type="secondary" className="text-xs">
                  在掘金客户端「交易」→「账户管理」中获取；token 视同密码，仅保存加密副本
                </Typography.Text>
              }
            >
              <Input.Password placeholder="掘金客户端「账户管理」中获取" />
            </Form.Item>
            <Space className="pt-1">
              <Button
                type="primary"
                htmlType="submit"
                loading={saveMutation.isPending}
              >
                {editing ? '保存修改' : '确认添加'}
              </Button>
              <Button onClick={backToList}>取消</Button>
            </Space>
          </Form>
        </div>
      )}
    </Modal>
  )
}
