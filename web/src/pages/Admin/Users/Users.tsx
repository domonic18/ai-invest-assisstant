import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  DeleteOutlined,
  DollarOutlined,
  EditOutlined,
  KeyOutlined,
  PlusOutlined,
} from '@ant-design/icons'
import {
  Button,
  Card,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  message,
} from 'antd'
import type { TableColumnsType } from 'antd'
import dayjs from 'dayjs'
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import {
  useAdminUsers,
  useCreateAdminUser,
  useDeleteAdminUser,
  useResetAdminUserPassword,
  useUpdateAdminUser,
} from '@/hooks/useAdminUsers'
import { PAGE_SIZE, type AdminUser } from '@ai-invest/shared'

import { ApproveModal, QuotaAdjustModal, RejectModal } from './components/AccountModals'
import { PendingPanel } from './components/PendingPanel'

interface UserFormValues {
  username: string
  email: string
  password?: string
  role: string
  isActive: boolean
}

const ROLE_OPTIONS = [
  { label: '普通用户', value: 'user' },
  { label: '管理员', value: 'admin' },
  { label: '分析师', value: 'analyst' },
]

// URL ?status= 驱动（无参数默认 pending：管理员进页第一眼即待办）
const STATUS_OPTIONS = [
  { label: '待审批', value: 'pending' },
  { label: '全部', value: 'all' },
  { label: '正常', value: 'approved' },
  { label: '已驳回', value: 'rejected' },
]

const STATUS_TAGS: Record<string, { color: string; label: string }> = {
  pending: { color: 'gold', label: '待审批' },
  approved: { color: 'green', label: '正常' },
  rejected: { color: 'red', label: '已驳回' },
}

function formatQuota(value: number | null) {
  return value == null ? '不限' : value.toLocaleString('zh-CN')
}

export function AdminUsers() {
  const [form] = Form.useForm<UserFormValues>()
  const [pwdForm] = Form.useForm<{ password: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const statusFilter = searchParams.get('status') ?? 'pending'
  const [params, setParams] = useState<{
    page: number
    pageSize: number
    status: string | null
  }>({ page: 1, pageSize: PAGE_SIZE.table, status: statusFilter })
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<AdminUser | null>(null)
  const [resetting, setResetting] = useState<AdminUser | null>(null)
  const [approving, setApproving] = useState<AdminUser | null>(null)
  const [rejecting, setRejecting] = useState<AdminUser | null>(null)
  const [adjustingQuota, setAdjustingQuota] = useState<AdminUser | null>(null)

  const { data, isLoading } = useAdminUsers({
    ...params,
    status: params.status === 'all' ? null : params.status,
  })
  const createMutation = useCreateAdminUser()
  const updateMutation = useUpdateAdminUser()
  const deleteMutation = useDeleteAdminUser()
  const resetMutation = useResetAdminUserPassword()

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    setModalOpen(true)
  }

  const openEdit = (user: AdminUser) => {
    setEditing(user)
    form.setFieldsValue({
      username: user.username,
      email: user.email,
      role: user.role,
      isActive: user.isActive,
    })
    setModalOpen(true)
  }

  const handleSubmit = async (values: UserFormValues) => {
    try {
      if (editing) {
        await updateMutation.mutateAsync({
          id: editing.id,
          data: {
            username: values.username,
            email: values.email,
            role: values.role,
            isActive: values.isActive,
          },
        })
        message.success('用户已更新')
      } else {
        await createMutation.mutateAsync({
          username: values.username,
          email: values.email,
          password: values.password || '',
          role: values.role,
          isActive: values.isActive,
        })
        message.success('用户已创建')
      }
      setModalOpen(false)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '操作失败')
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await deleteMutation.mutateAsync(id)
      message.success('用户已删除')
    } catch (err) {
      message.error(err instanceof Error ? err.message : '删除失败')
    }
  }

  const handleResetPassword = async (values: { password: string }) => {
    if (!resetting) return
    try {
      await resetMutation.mutateAsync({ id: resetting.id, data: values })
      message.success('密码已重置')
      setResetting(null)
      pwdForm.resetFields()
    } catch (err) {
      message.error(err instanceof Error ? err.message : '重置失败')
    }
  }

  const columns: TableColumnsType<AdminUser> = [
    { title: '用户名', dataIndex: 'username', key: 'username' },
    { title: '邮箱', dataIndex: 'email', key: 'email', ellipsis: true },
    { title: '角色', dataIndex: 'role', key: 'role', width: 84 },
    {
      title: '账号状态',
      dataIndex: 'status',
      key: 'status',
      width: 96,
      render: (value: string, record: AdminUser) => {
        const tag = STATUS_TAGS[value] ?? { color: 'default', label: value }
        return (
          <Space size={4}>
            <Tag color={tag.color}>{tag.label}</Tag>
            {!record.isActive && <Tag>已禁用</Tag>}
          </Space>
        )
      },
    },
    {
      title: '剩余配额',
      dataIndex: 'remainingQuota',
      key: 'remainingQuota',
      width: 110,
      align: 'right',
      render: (value: number | null, record: AdminUser) => (
        <span className={record.byokEnabled ? 'text-[#5c616e]' : ''}>
          {formatQuota(value)}
          {record.byokEnabled && (
            <Tag bordered={false} color="green" className="!ml-1">
              自有 Key
            </Tag>
          )}
        </span>
      ),
    },
    {
      title: '累计消耗',
      dataIndex: 'totalUsed',
      key: 'totalUsed',
      width: 100,
      align: 'right',
      render: (value: number) => value.toLocaleString('zh-CN'),
    },
    {
      title: '申请说明',
      dataIndex: 'applicationNote',
      key: 'applicationNote',
      ellipsis: true,
      render: (value: string | null, record: AdminUser) =>
        value ?? (record.rejectReason ? <Tag color="red">驳回：{record.rejectReason}</Tag> : '-'),
    },
    {
      title: '创建时间',
      dataIndex: 'createdAt',
      key: 'createdAt',
      width: 150,
      render: (value: string) => dayjs(value).format('YYYY-MM-DD HH:mm'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 260,
      render: (_: unknown, record: AdminUser) => (
        <Space size={4} wrap>
          {record.status === 'pending' && (
            <>
              <Button
                size="small"
                type="primary"
                icon={<CheckCircleOutlined />}
                onClick={() => setApproving(record)}
              >
                通过
              </Button>
              <Button
                size="small"
                danger
                icon={<CloseCircleOutlined />}
                onClick={() => setRejecting(record)}
              >
                驳回
              </Button>
            </>
          )}
          {record.status === 'approved' && (
            <Button
              size="small"
              icon={<DollarOutlined />}
              onClick={() => setAdjustingQuota(record)}
            >
              配额
            </Button>
          )}
          <Button
            size="small"
            icon={<KeyOutlined />}
            onClick={() => setResetting(record)}
          >
            重置密码
          </Button>
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => openEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm title="确认删除？" onConfirm={() => handleDelete(record.id)}>
            <Button size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div className="space-y-4">
      <PendingPanel />
      <Card
        title="用户管理"
        variant="borderless"
        extra={
          <Space>
            <Select
              value={statusFilter === 'all' ? 'all' : statusFilter}
              options={STATUS_OPTIONS}
              onChange={(value) => {
                setSearchParams(value === 'all' ? { status: 'all' } : { status: value }, { replace: true })
                setParams((prev) => ({ ...prev, page: 1, status: value }))
              }}
              style={{ width: 110 }}
            />
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
              新增用户
            </Button>
          </Space>
        }
      >
      <Table
        dataSource={data?.items || []}
        columns={columns}
        rowKey="id"
        loading={isLoading}
        scroll={{ x: 1200 }}
        pagination={{
          current: data?.page,
          pageSize: data?.pageSize,
          total: data?.total,
          onChange: (page, pageSize) => setParams((prev) => ({ ...prev, page, pageSize })),
        }}
      />

      <Modal
        title={editing ? '编辑用户' : '新增用户'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={createMutation.isPending || updateMutation.isPending}
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item
            name="username"
            label="用户名"
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="email"
            label="邮箱"
            rules={[
              { required: true, message: '请输入邮箱' },
              { type: 'email', message: '邮箱格式不正确' },
            ]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="password"
            label="密码"
            rules={[
              { required: !editing, message: '请输入密码' },
              { min: 6, message: '密码至少 6 位' },
            ]}
          >
            <Input.Password />
          </Form.Item>
          <Form.Item
            name="role"
            label="角色"
            rules={[{ required: true, message: '请选择角色' }]}
          >
            <Select options={ROLE_OPTIONS} />
          </Form.Item>
          <Form.Item name="isActive" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`重置密码 - ${resetting?.username || ''}`}
        open={!!resetting}
        onCancel={() => {
          setResetting(null)
          pwdForm.resetFields()
        }}
        onOk={() => pwdForm.submit()}
        confirmLoading={resetMutation.isPending}
      >
        <Form form={pwdForm} layout="vertical" onFinish={handleResetPassword}>
          <Form.Item
            name="password"
            label="新密码"
            rules={[{ required: true, min: 6 }]}
          >
            <Input.Password />
          </Form.Item>
        </Form>
      </Modal>

      </Card>

      <ApproveModal user={approving} onClose={() => setApproving(null)} />
      <RejectModal user={rejecting} onClose={() => setRejecting(null)} />
      <QuotaAdjustModal user={adjustingQuota} onClose={() => setAdjustingQuota(null)} />
    </div>
  )
}
