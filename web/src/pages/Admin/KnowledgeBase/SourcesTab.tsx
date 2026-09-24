import {
  Button,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import { useState } from 'react'

import type { ApiKbSourceResponse } from '@ai-invest/shared'
import dayjs from 'dayjs'

import {
  useCreateKbSource,
  useDeleteKbSource,
  useKbSources,
  useRestoreKbSource,
  useUpdateKbSource,
} from '@/hooks/useAdminKb'
import { formatBytes, formatDateTime } from '@/utils/formatters'

interface SourceFormValues {
  sourceType: 'course' | 'book'
  name: string
  author?: string
  description?: string
  enabled: boolean
}

export function SourcesTab({ onOpenIngest }: { onOpenIngest: (sourceId: number) => void }) {
  const { data: sources = [], isLoading } = useKbSources()
  const createMutation = useCreateKbSource()
  const updateMutation = useUpdateKbSource()
  const deleteMutation = useDeleteKbSource()
  const restoreMutation = useRestoreKbSource()

  const [form] = Form.useForm<SourceFormValues>()
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<ApiKbSourceResponse | null>(null)
  const [deletedCache, setDeletedCache] = useState<ApiKbSourceResponse | null>(null)

  const openCreate = () => {
    setEditing(null)
    form.setFieldsValue({
      sourceType: 'course',
      name: '',
      author: '',
      description: '',
      enabled: true,
    })
    setModalOpen(true)
  }

  const openEdit = (row: ApiKbSourceResponse) => {
    setEditing(row)
    form.setFieldsValue({
      sourceType: row.sourceType,
      name: row.name,
      author: row.author ?? '',
      description: row.description ?? '',
      enabled: row.enabled,
    })
    setModalOpen(true)
  }

  const handleSubmit = async (values: SourceFormValues) => {
    try {
      if (editing) {
        await updateMutation.mutateAsync({
          id: editing.id,
          data: {
            name: values.name,
            author: values.author || null,
            description: values.description || null,
            enabled: values.enabled,
          },
        })
        message.success('知识库已更新')
      } else {
        await createMutation.mutateAsync({
          sourceType: values.sourceType,
          name: values.name,
          author: values.author || null,
          description: values.description || null,
          enabled: values.enabled,
        })
        message.success('知识库已创建，可前往「素材接入」上传')
      }
      setModalOpen(false)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '保存失败')
    }
  }

  const handleDelete = async (row: ApiKbSourceResponse) => {
    try {
      await deleteMutation.mutateAsync(row.id)
      setDeletedCache(row)
      message.success('已软删（24 小时内可恢复）')
    } catch (err) {
      message.error(err instanceof Error ? err.message : '删除失败')
    }
  }

  const handleRestore = async () => {
    if (!deletedCache) return
    try {
      await restoreMutation.mutateAsync(deletedCache.id)
      message.success('已恢复')
    } catch (err) {
      message.error(err instanceof Error ? err.message : '恢复失败（可能已超过 24 小时窗口）')
    } finally {
      setDeletedCache(null)
    }
  }

  const columns: ColumnsType<ApiKbSourceResponse> = [
    {
      title: '名称',
      dataIndex: 'name',
      render: (name: string, row) => (
        <div>
          <div className="flex items-center gap-2">
            {name}
            <Tag>{row.sourceType === 'course' ? '课程' : '电子书'}</Tag>
            {!row.enabled && <Tag color="warning">已停用</Tag>}
          </div>
          {row.description && (
            <Typography.Text type="secondary" className="text-xs" ellipsis>
              {row.description}
            </Typography.Text>
          )}
        </div>
      ),
    },
    { title: '作者', dataIndex: 'author', width: 120, render: (v: string | null) => v ?? '-' },
    {
      title: '已用存储',
      dataIndex: 'storageBytes',
      width: 110,
      render: (v: number) => formatBytes(v),
    },
    {
      title: '待清理',
      dataIndex: 'pendingCleanupBytes',
      width: 110,
      render: (v: number) => (v > 0 ? formatBytes(v) : '-'),
    },
    {
      title: '创建时间',
      dataIndex: 'createdAt',
      width: 150,
      render: (v: string) => formatDateTime(v),
    },
    {
      title: '操作',
      key: 'actions',
      width: 240,
      render: (_: unknown, row) => (
        <Space size="small">
          <Button size="small" type="link" onClick={() => onOpenIngest(row.id)}>
            素材接入
          </Button>
          <Button size="small" type="link" onClick={() => openEdit(row)}>
            编辑
          </Button>
          <Popconfirm
            title="确认删除该知识库？"
            description="素材与文稿将一并隐藏，24 小时内可恢复"
            onConfirm={() => handleDelete(row)}
          >
            <Button size="small" type="link" danger>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <Typography.Text type="secondary">
          {deletedCache && (
            <Space>
              <span>
                「{deletedCache.name}」已进入 24h 恢复窗（
                {dayjs(deletedCache.updatedAt).add(24, 'hour').format('HH:mm')} 前可恢复）
              </span>
              <Button size="small" icon={<ReloadOutlined />} onClick={handleRestore}>
                撤销删除
              </Button>
            </Space>
          )}
        </Typography.Text>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新建知识库
        </Button>
      </div>

      <Table
        size="small"
        rowKey="id"
        columns={columns}
        dataSource={sources}
        loading={isLoading}
        pagination={false}
      />

      <Modal
        title={editing ? `编辑知识库 · ${editing.name}` : '新建知识库'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={createMutation.isPending || updateMutation.isPending}
        destroyOnClose
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item
            name="sourceType"
            label="类型"
            rules={[{ required: true }]}
            extra="创建后不可更改：课程 = 视频/音频按集转写；电子书 = 文档按页解析"
          >
            <Select
              disabled={editing != null}
              options={[
                { value: 'course', label: '课程（视频/音频）' },
                { value: 'book', label: '电子书（PDF/EPUB）' },
              ]}
            />
          </Form.Item>
          <Form.Item
            name="name"
            label="名称"
            rules={[{ required: true, message: '请输入名称' }]}
          >
            <Input maxLength={200} />
          </Form.Item>
          <Form.Item name="author" label="作者">
            <Input maxLength={100} />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} maxLength={2000} />
          </Form.Item>
          <Form.Item name="enabled" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
