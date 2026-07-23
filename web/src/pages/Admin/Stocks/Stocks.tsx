import { DeleteOutlined, EditOutlined, PlusOutlined, SearchOutlined } from '@ant-design/icons'
import {
  Button,
  Card,
  DatePicker,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  message,
} from 'antd'
import type { Dayjs } from 'dayjs'
import dayjs from 'dayjs'
import { useState } from 'react'

import {
  useAdminStocks,
  useCreateAdminStock,
  useDeleteAdminStock,
  useUpdateAdminStock,
} from '@/hooks/useAdminStocks'
import type { AdminStock } from '@ai-invest/shared'

interface StockFormValues {
  stockCode: string
  stockName: string
  market: 'sh' | 'sz' | 'bj'
  industryL1?: string
  industryL2?: string
  industryL3?: string
  listingDate?: Dayjs | null
}

const MARKET_OPTIONS = [
  { label: '上交所', value: 'sh' },
  { label: '深交所', value: 'sz' },
  { label: '北交所', value: 'bj' },
]

export function AdminStocks() {
  const [form] = Form.useForm<StockFormValues>()
  const [params, setParams] = useState({ q: '', page: 1, pageSize: 20 })
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<AdminStock | null>(null)

  const { data, isLoading } = useAdminStocks(params)
  const createMutation = useCreateAdminStock()
  const updateMutation = useUpdateAdminStock()
  const deleteMutation = useDeleteAdminStock()

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    setModalOpen(true)
  }

  const openEdit = (stock: AdminStock) => {
    setEditing(stock)
    form.setFieldsValue({
      stockCode: stock.stockCode,
      stockName: stock.stockName,
      market: stock.market as 'sh' | 'sz' | 'bj',
      industryL1: stock.industryL1 || undefined,
      industryL2: stock.industryL2 || undefined,
      industryL3: stock.industryL3 || undefined,
      listingDate: stock.listingDate ? dayjs(stock.listingDate) : null,
    })
    setModalOpen(true)
  }

  const handleSubmit = async (values: StockFormValues) => {
    const payload = {
      stock_code: values.stockCode,
      stock_name: values.stockName,
      market: values.market,
      industry_level_1: values.industryL1,
      industry_level_2: values.industryL2,
      industry_level_3: values.industryL3,
      listing_date: values.listingDate
        ? values.listingDate.format('YYYY-MM-DD')
        : undefined,
    }
    try {
      if (editing) {
        await updateMutation.mutateAsync({ id: editing.id, data: payload })
        message.success('股票已更新')
      } else {
        await createMutation.mutateAsync(payload)
        message.success('股票已创建')
      }
      setModalOpen(false)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '操作失败')
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await deleteMutation.mutateAsync(id)
      message.success('股票已删除')
    } catch (err) {
      message.error(err instanceof Error ? err.message : '删除失败')
    }
  }

  const columns = [
    { title: '股票代码', dataIndex: 'stockCode', key: 'stockCode' },
    { title: '股票名称', dataIndex: 'stockName', key: 'stockName' },
    { title: '公司全称', dataIndex: 'fullName', key: 'fullName', ellipsis: true, render: (v: string | null) => v || '-' },
    { title: '市场', dataIndex: 'market', key: 'market' },
    { title: '一级行业', dataIndex: 'industryL1', key: 'industryL1', render: (v: string | null) => v || '-' },
    { title: '二级行业', dataIndex: 'industryL2', key: 'industryL2', render: (v: string | null) => v || '-' },
    { title: '三级行业', dataIndex: 'industryL3', key: 'industryL3', render: (v: string | null) => v || '-' },
    { title: '上市日期', dataIndex: 'listingDate', key: 'listingDate', render: (v: string | null) => v || '-' },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: AdminStock) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>
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
      title="股票管理"
      variant="borderless"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新增股票
        </Button>
      }
    >
      <Input.Search
        placeholder="搜索代码或名称"
        allowClear
        className="mb-4 max-w-sm"
        enterButton={<SearchOutlined />}
        onSearch={(value) => setParams((prev) => ({ ...prev, q: value, page: 1 }))}
      />

      <Table
        dataSource={data?.items || []}
        columns={columns}
        rowKey="id"
        loading={isLoading}
        pagination={{
          current: data?.page,
          pageSize: data?.pageSize,
          total: data?.total,
          onChange: (page, pageSize) => setParams({ ...params, page, pageSize }),
        }}
      />

      <Modal
        title={editing ? '编辑股票' : '新增股票'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={createMutation.isPending || updateMutation.isPending}
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item
            name="stockCode"
            label="股票代码"
            rules={[{ required: true }]}
          >
            <Input disabled={!!editing} />
          </Form.Item>
          <Form.Item
            name="stockName"
            label="股票名称"
            rules={[{ required: true }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="market"
            label="市场"
            rules={[{ required: true }]}
          >
            <Select options={MARKET_OPTIONS} />
          </Form.Item>
          <Form.Item name="industryL1" label="一级行业">
            <Input />
          </Form.Item>
          <Form.Item name="industryL2" label="二级行业">
            <Input />
          </Form.Item>
          <Form.Item name="industryL3" label="三级行业">
            <Input />
          </Form.Item>
          <Form.Item name="listingDate" label="上市日期">
            <DatePicker />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  )
}
