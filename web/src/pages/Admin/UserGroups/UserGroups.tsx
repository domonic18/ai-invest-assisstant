import { DeleteOutlined, EditOutlined, PlusOutlined } from '@ant-design/icons'
import {
  Button,
  Card,
  Checkbox,
  Form,
  Input,
  Modal,
  Popconfirm,
  Space,
  Switch,
  Table,
  Tag,
  message,
} from 'antd'
import type { TableColumnsType } from 'antd'
import dayjs from 'dayjs'
import { useState } from 'react'

import {
  FEATURE_CATALOG,
  FEATURE_CATEGORIES,
  FEATURE_KEYS,
  type ApiUserGroupResponse,
} from '@ai-invest/shared'

import {
  useAdminUserGroups,
  useCreateAdminUserGroup,
  useDeleteAdminUserGroup,
  useUpdateAdminUserGroup,
} from '@/hooks/useAdminUserGroups'

interface GroupFormValues {
  name: string
  description?: string
  isActive: boolean
  permissions: string[]
}

const LABEL_BY_KEY: Record<string, string> = FEATURE_CATALOG.reduce(
  (acc, item) => {
    acc[item.key] = item.label
    return acc
  },
  {} as Record<string, string>
)

/** 权限勾选：按分类分组 + 顶部全选；作为 Form.Item 自定义受控组件（value/onChange 注入）。 */
function PermissionGroups({
  value = [],
  onChange,
}: {
  value?: string[]
  onChange?: (v: string[]) => void
}) {
  const allKeys: readonly string[] = FEATURE_KEYS
  const checkedCount = allKeys.filter((k) => value.includes(k)).length
  const allChecked = checkedCount === allKeys.length

  return (
    <div className="space-y-3">
      <Checkbox
        checked={allChecked}
        indeterminate={checkedCount > 0 && !allChecked}
        onChange={(e) => onChange?.(e.target.checked ? [...allKeys] : [])}
      >
        全选（{checkedCount}/{allKeys.length}）
      </Checkbox>
      {FEATURE_CATEGORIES.map(({ category, items }) => (
        <div key={category}>
          <div className="text-xs text-gray-500 mb-1">{category}</div>
          <Checkbox.Group
            className="flex flex-col gap-1"
            options={items.map((item) => ({ label: item.label, value: item.key }))}
            value={items.filter((item) => value.includes(item.key)).map((item) => item.key)}
            onChange={(checked) => {
              const others = value.filter((k) => !items.some((item) => item.key === k))
              onChange?.([...others, ...checked])
            }}
          />
        </div>
      ))}
    </div>
  )
}

export function AdminUserGroups() {
  const [form] = Form.useForm<GroupFormValues>()
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<ApiUserGroupResponse | null>(null)

  const { data: groups, isLoading } = useAdminUserGroups()
  const createMutation = useCreateAdminUserGroup()
  const updateMutation = useUpdateAdminUserGroup()
  const deleteMutation = useDeleteAdminUserGroup()

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    form.setFieldsValue({ isActive: true, permissions: [] })
    setModalOpen(true)
  }

  const openEdit = (group: ApiUserGroupResponse) => {
    setEditing(group)
    form.setFieldsValue({
      name: group.name,
      description: group.description ?? undefined,
      isActive: group.isActive,
      permissions: group.permissions,
    })
    setModalOpen(true)
  }

  const handleSubmit = async (values: GroupFormValues) => {
    try {
      if (editing) {
        await updateMutation.mutateAsync({
          id: editing.id,
          data: {
            name: values.name,
            description: values.description ?? null,
            isActive: values.isActive,
            permissions: values.permissions,
          },
        })
        message.success('用户组已更新')
      } else {
        await createMutation.mutateAsync({
          name: values.name,
          description: values.description ?? null,
          permissions: values.permissions,
        })
        message.success('用户组已创建')
      }
      setModalOpen(false)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '操作失败')
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await deleteMutation.mutateAsync(id)
      message.success('用户组已删除')
    } catch (err) {
      message.error(err instanceof Error ? err.message : '删除失败')
    }
  }

  const columns: TableColumnsType<ApiUserGroupResponse> = [
    { title: '名称', dataIndex: 'name', key: 'name', width: 160 },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    {
      title: '功能权限',
      dataIndex: 'permissions',
      key: 'permissions',
      render: (value: string[]) =>
        value.length ? (
          <Space size={4} wrap>
            {value.map((key) => (
              <Tag key={key} bordered={false} color="blue">
                {LABEL_BY_KEY[key] ?? key}
              </Tag>
            ))}
          </Space>
        ) : (
          <Tag>未开通任何功能（受限）</Tag>
        ),
    },
    {
      title: '状态',
      dataIndex: 'isActive',
      key: 'isActive',
      width: 90,
      render: (value: boolean) =>
        value ? <Tag color="green">启用</Tag> : <Tag color="red">停用</Tag>,
    },
    {
      title: '更新时间',
      dataIndex: 'updatedAt',
      key: 'updatedAt',
      width: 150,
      render: (value: string) => dayjs(value).format('YYYY-MM-DD HH:mm'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 150,
      render: (_: unknown, record: ApiUserGroupResponse) => (
        <Space size={4}>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>
            编辑
          </Button>
          <Popconfirm
            title="确认删除该用户组？"
            description="组内仍有用户时将无法删除"
            onConfirm={() => handleDelete(record.id)}
          >
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
      title="用户组"
      variant="borderless"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新增用户组
        </Button>
      }
    >
      <Table
        dataSource={groups || []}
        columns={columns}
        rowKey="id"
        loading={isLoading}
        pagination={false}
      />

      <Modal
        title={editing ? '编辑用户组' : '新增用户组'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={createMutation.isPending || updateMutation.isPending}
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item
            name="name"
            label="名称"
            rules={[
              { required: true, message: '请输入用户组名称' },
              { max: 50, message: '名称不超过 50 字符' },
            ]}
          >
            <Input placeholder="如：外部试用" />
          </Form.Item>
          <Form.Item name="description" label="描述" rules={[{ max: 200 }]}>
            <Input.TextArea placeholder="选填" rows={2} />
          </Form.Item>
          <Form.Item name="permissions" label="功能权限">
            <PermissionGroups />
          </Form.Item>
          <Form.Item
            name="isActive"
            label="启用"
            valuePropName="checked"
            extra="停用后该组成员立即失去全部功能权限（admin 不受影响）"
          >
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  )
}
