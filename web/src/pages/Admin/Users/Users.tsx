import {
  DeleteOutlined,
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
import dayjs from 'dayjs'
import { useState } from 'react'

import {
  useAdminUsers,
  useCreateAdminUser,
  useDeleteAdminUser,
  useResetAdminUserPassword,
  useUpdateAdminUser,
} from '@/hooks/useAdminUsers'
import type { AdminUser } from '@ai-invest/shared'

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

export function AdminUsers() {
  const [form] = Form.useForm<UserFormValues>()
  const [pwdForm] = Form.useForm<{ password: string }>()
  const [params, setParams] = useState({ page: 1, pageSize: 20 })
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<AdminUser | null>(null)
  const [resetting, setResetting] = useState<AdminUser | null>(null)

  const { data, isLoading } = useAdminUsers(params)
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
            is_active: values.isActive,
          },
        })
        message.success('用户已更新')
      } else {
        await createMutation.mutateAsync({
          username: values.username,
          email: values.email,
          password: values.password || '',
          role: values.role,
          is_active: values.isActive,
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

  const columns = [
    { title: '用户名', dataIndex: 'username', key: 'username' },
    { title: '邮箱', dataIndex: 'email', key: 'email' },
    { title: '角色', dataIndex: 'role', key: 'role' },
    {
      title: '状态',
      dataIndex: 'isActive',
      key: 'isActive',
      render: (value: boolean) =>
        value ? <Tag color="green">启用</Tag> : <Tag>禁用</Tag>,
    },
    {
      title: '创建时间',
      dataIndex: 'createdAt',
      key: 'createdAt',
      render: (value: string) => dayjs(value).format('YYYY-MM-DD HH:mm:ss'),
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: AdminUser) => (
        <Space>
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
    <Card
      title="用户管理"
      variant="borderless"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新增用户
        </Button>
      }
    >
      <Table
        dataSource={data?.items || []}
        columns={columns}
        rowKey="id"
        loading={isLoading}
        pagination={{
          current: data?.page,
          pageSize: data?.pageSize,
          total: data?.total,
          onChange: (page, pageSize) => setParams({ page, pageSize }),
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
  )
}
