/**
 * 题材（股票-概念）映射管理：同花顺概念成分股映射的运营修正入口。
 * 同步链路写 source=ths，此处增改标记 source=manual；(股票, 概念代码) 唯一，
 * 冲突 409 由 axios 拦截器统一提示。
 */
import { DeleteOutlined, EditOutlined, PlusOutlined, SearchOutlined } from '@ant-design/icons'
import {
  Button,
  Card,
  Form,
  Input,
  Modal,
  Popconfirm,
  Space,
  Table,
  Tag,
  Tooltip,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useState } from 'react'

import {
  useAdminStockConcepts,
  useCreateAdminStockConcept,
  useDeleteAdminStockConcept,
  useUpdateAdminStockConcept,
} from '@/hooks/useAdminStockConcepts'
import { PAGE_SIZE, type AdminStockConcept } from '@ai-invest/shared'
import { formatDateTime } from '@/utils/formatters'

interface ConceptFormValues {
  stockCode: string
  conceptCode: string
  conceptName: string
}

export function StockConcepts() {
  const [form] = Form.useForm<ConceptFormValues>()
  const [params, setParams] = useState({
    q: '',
    concept: '',
    page: 1,
    pageSize: PAGE_SIZE.table,
  })
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<AdminStockConcept | null>(null)

  const { data, isLoading } = useAdminStockConcepts(params)
  const createMutation = useCreateAdminStockConcept()
  const updateMutation = useUpdateAdminStockConcept()
  const deleteMutation = useDeleteAdminStockConcept()

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    setModalOpen(true)
  }

  const openEdit = (row: AdminStockConcept) => {
    setEditing(row)
    form.setFieldsValue({
      stockCode: row.stockCode,
      conceptCode: row.conceptCode,
      conceptName: row.conceptName,
    })
    setModalOpen(true)
  }

  const handleSubmit = async (values: ConceptFormValues) => {
    try {
      if (editing) {
        await updateMutation.mutateAsync({ id: editing.id, data: values })
        message.success('映射已更新')
      } else {
        await createMutation.mutateAsync(values)
        message.success('映射已创建')
      }
      setModalOpen(false)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '操作失败')
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await deleteMutation.mutateAsync(id)
      message.success('映射已删除')
    } catch (err) {
      message.error(err instanceof Error ? err.message : '删除失败')
    }
  }

  const columns: ColumnsType<AdminStockConcept> = [
    { title: '股票代码', dataIndex: 'stockCode', width: 110 },
    { title: '股票名称', dataIndex: 'stockName', width: 120, render: (v: string | null) => v || '-' },
    { title: '概念代码', dataIndex: 'conceptCode', width: 110 },
    { title: '概念名称', dataIndex: 'conceptName', ellipsis: true },
    {
      title: '来源',
      dataIndex: 'source',
      width: 90,
      render: (v: string) =>
        v === 'manual' ? <Tag color="gold">手工</Tag> : <Tag>ths 同步</Tag>,
    },
    {
      title: '更新时间',
      dataIndex: 'updatedAt',
      width: 160,
      render: (v: string) => formatDateTime(v),
    },
    {
      title: '操作',
      key: 'actions',
      width: 140,
      fixed: 'right' as const,
      render: (_, record) => (
        <Space size={4}>
          <Tooltip title="编辑">
            <Button
              size="small"
              aria-label="编辑"
              icon={<EditOutlined />}
              onClick={() => openEdit(record)}
            />
          </Tooltip>
          <Popconfirm title="确认删除该映射？" onConfirm={() => void handleDelete(record.id)}>
            <Tooltip title="删除">
              <Button size="small" danger aria-label="删除" icon={<DeleteOutlined />} />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <Card
      title="题材映射管理"
      variant="borderless"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新增映射
        </Button>
      }
    >
      <Space className="mb-4" wrap>
        <Input
          placeholder="股票代码精确过滤"
          allowClear
          style={{ width: 180 }}
          onPressEnter={(e) =>
            setParams((prev) => ({
              ...prev,
              q: (e.target as HTMLInputElement).value.trim(),
              page: 1,
            }))
          }
          onChange={(e) => {
            if (!e.target.value) setParams((prev) => ({ ...prev, q: '', page: 1 }))
          }}
        />
        <Input.Search
          placeholder="搜索概念名称/代码"
          allowClear
          enterButton={<SearchOutlined />}
          style={{ width: 260 }}
          onSearch={(value) =>
            setParams((prev) => ({ ...prev, concept: value.trim(), page: 1 }))
          }
        />
      </Space>

      <Table<AdminStockConcept>
        dataSource={data?.items || []}
        columns={columns}
        rowKey="id"
        loading={isLoading}
        scroll={{ x: 'max-content' }}
        pagination={{
          current: data?.page,
          pageSize: data?.pageSize,
          total: data?.total,
          onChange: (page, pageSize) => setParams({ ...params, page, pageSize }),
        }}
      />

      <Modal
        title={editing ? '编辑映射' : '新增映射'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={createMutation.isPending || updateMutation.isPending}
        width={480}
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item
            name="stockCode"
            label="股票代码"
            rules={[{ required: true, message: '请输入 6 位股票代码' }]}
          >
            <Input placeholder="如 600703" maxLength={10} />
          </Form.Item>
          <Form.Item
            name="conceptCode"
            label="概念代码"
            rules={[{ required: true, message: '请输入概念代码' }]}
          >
            <Input placeholder="同花顺概念代码，如 881234" maxLength={20} />
          </Form.Item>
          <Form.Item
            name="conceptName"
            label="概念名称"
            rules={[{ required: true, message: '请输入概念名称' }]}
          >
            <Input placeholder="如 Mini LED" maxLength={100} />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  )
}
