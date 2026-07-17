import { DeleteOutlined, EditOutlined, PlusOutlined, SearchOutlined } from '@ant-design/icons'
import {
  Button,
  Card,
  DatePicker,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Typography,
  message,
} from 'antd'
import type { Dayjs } from 'dayjs'
import dayjs from 'dayjs'
import { useState } from 'react'
import type { ColumnsType } from 'antd/es/table'

import {
  useAdminReports,
  useCreateAdminReport,
  useDeleteAdminReport,
  useUpdateAdminReport,
} from '@/hooks/useAdminReports'
import type { AdminReport } from '@ai-invest/shared'

interface ReportFormValues {
  filePath: string
  originalName?: string
  fileType: string
  stockCode?: string
  reportDate?: Dayjs | null
  reportType?: string
  broker?: string
  fileSize?: number | null
  md5Hash?: string
  downloadUrl?: string
}

interface FilterForm {
  stockCode?: string
  fileType?: string
}

const FILE_TYPE_OPTIONS = [
  { label: '财报', value: 'financial_report' },
  { label: '研报', value: 'research_report' },
  { label: '公告', value: 'announcement' },
  { label: '图片', value: 'image' },
]

function formatFileSize(bytes: number | null): string {
  if (bytes === null || bytes === undefined) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

export function AdminReports() {
  const [form] = Form.useForm<ReportFormValues>()
  const [filter] = Form.useForm<FilterForm>()
  const [params, setParams] = useState({ stockCode: '', fileType: '', page: 1, pageSize: 20 })
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<AdminReport | null>(null)

  const { data, isLoading } = useAdminReports(params)
  const createMutation = useCreateAdminReport()
  const updateMutation = useUpdateAdminReport()
  const deleteMutation = useDeleteAdminReport()

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    setModalOpen(true)
  }

  const openEdit = (report: AdminReport) => {
    setEditing(report)
    form.setFieldsValue({
      filePath: report.filePath,
      originalName: report.originalName || undefined,
      fileType: report.fileType,
      stockCode: report.stockCode || undefined,
      reportDate: report.reportDate ? dayjs(report.reportDate) : null,
      reportType: report.reportType || undefined,
      broker: report.broker || undefined,
      fileSize: report.fileSize,
      md5Hash: report.md5Hash || undefined,
      downloadUrl: report.downloadUrl || undefined,
    })
    setModalOpen(true)
  }

  const handleSubmit = async (values: ReportFormValues) => {
    const payload = {
      file_path: values.filePath,
      original_name: values.originalName,
      file_type: values.fileType,
      stock_code: values.stockCode,
      report_date: values.reportDate ? values.reportDate.format('YYYY-MM-DD') : undefined,
      report_type: values.reportType,
      broker: values.broker,
      file_size: values.fileSize ?? undefined,
      md5_hash: values.md5Hash,
      download_url: values.downloadUrl,
    }
    try {
      if (editing) {
        await updateMutation.mutateAsync({ id: editing.id, data: payload })
        message.success('报告已更新')
      } else {
        await createMutation.mutateAsync(payload)
        message.success('报告已创建')
      }
      setModalOpen(false)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '操作失败')
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await deleteMutation.mutateAsync(id)
      message.success('报告已删除')
    } catch (err) {
      message.error(err instanceof Error ? err.message : '删除失败')
    }
  }

  const handleSearch = (values: FilterForm) => {
    setParams({
      stockCode: values.stockCode || '',
      fileType: values.fileType || '',
      page: 1,
      pageSize: params.pageSize,
    })
  }

  const columns: ColumnsType<AdminReport> = [
    { title: '文件路径', dataIndex: 'filePath', key: 'filePath', ellipsis: true },
    { title: '原文件名', dataIndex: 'originalName', key: 'originalName', render: (v: string | null) => v || '-' },
    { title: '类型', dataIndex: 'fileType', key: 'fileType' },
    { title: '股票代码', dataIndex: 'stockCode', key: 'stockCode', render: (v: string | null) => v || '-' },
    { title: '报告日期', dataIndex: 'reportDate', key: 'reportDate', render: (v: string | null) => v || '-' },
    { title: '报告类型', dataIndex: 'reportType', key: 'reportType', render: (v: string | null) => v || '-' },
    { title: '券商', dataIndex: 'broker', key: 'broker', render: (v: string | null) => v || '-' },
    { title: '大小', dataIndex: 'fileSize', key: 'fileSize', render: (v: number | null) => formatFileSize(v) },
    { title: '下载次数', dataIndex: 'downloadCount', key: 'downloadCount' },
    {
      title: '操作',
      key: 'actions',
      width: 190,
      fixed: 'right',
      render: (_: unknown, record: AdminReport) => (
        <Space>
          {record.downloadUrl && (
            <Typography.Link href={record.downloadUrl} target="_blank" rel="noreferrer">
              下载
            </Typography.Link>
          )}
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
      title="研报管理"
      variant="borderless"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新增报告
        </Button>
      }
    >
      <Form
        form={filter}
        layout="inline"
        onFinish={handleSearch}
        className="mb-4"
      >
        <Form.Item name="stockCode" label="股票代码">
          <Input placeholder="000001" allowClear />
        </Form.Item>
        <Form.Item name="fileType" label="文件类型">
          <Select options={FILE_TYPE_OPTIONS} allowClear placeholder="请选择" className="w-32" />
        </Form.Item>
        <Form.Item>
          <Button type="primary" htmlType="submit" icon={<SearchOutlined />}>
            查询
          </Button>
        </Form.Item>
      </Form>

      <Table
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
        title={editing ? '编辑报告' : '新增报告'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={createMutation.isPending || updateMutation.isPending}
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item name="filePath" label="文件路径" rules={[{ required: true }]}>
            <Input disabled={!!editing} />
          </Form.Item>
          <Form.Item name="originalName" label="原文件名">
            <Input />
          </Form.Item>
          <Form.Item name="fileType" label="文件类型" rules={[{ required: true }]}>
            <Select options={FILE_TYPE_OPTIONS} />
          </Form.Item>
          <Form.Item name="stockCode" label="股票代码">
            <Input />
          </Form.Item>
          <Form.Item name="reportDate" label="报告日期">
            <DatePicker />
          </Form.Item>
          <Form.Item name="reportType" label="报告类型">
            <Input />
          </Form.Item>
          <Form.Item name="broker" label="券商">
            <Input />
          </Form.Item>
          <Form.Item name="fileSize" label="文件大小（字节）">
            <InputNumber className="w-full" min={0} />
          </Form.Item>
          <Form.Item name="md5Hash" label="MD5">
            <Input />
          </Form.Item>
          <Form.Item name="downloadUrl" label="下载链接">
            <Input />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  )
}
