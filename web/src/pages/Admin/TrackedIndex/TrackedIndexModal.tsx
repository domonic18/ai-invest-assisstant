import { Form, Input, InputNumber, Modal, Select, Switch } from 'antd'
import { useEffect } from 'react'

import type { TrackedIndexConfig, TrackedIndexFormValues } from '@ai-invest/shared'

interface TrackedIndexModalProps {
  open: boolean
  editing: TrackedIndexConfig | null
  onCancel: () => void
  onSubmit: (values: TrackedIndexFormValues) => void
  loading: boolean
}

const CATEGORY_OPTIONS = [
  { value: 'A股', label: 'A 股' },
  { value: '全球', label: '全球' },
]

const SOURCE_OPTIONS = [
  { value: 'sina', label: '新浪财经' },
  { value: 'eastmoney', label: '东方财富' },
  { value: 'tushare', label: 'Tushare Pro' },
]

export function TrackedIndexModal({
  open,
  editing,
  onCancel,
  onSubmit,
  loading,
}: TrackedIndexModalProps) {
  const [form] = Form.useForm<TrackedIndexFormValues>()

  useEffect(() => {
    if (open) {
      if (editing) {
        form.setFieldsValue({
          indexCode: editing.indexCode,
          indexName: editing.indexName,
          marketCategory: editing.marketCategory,
          dataSource: editing.dataSource,
          sortOrder: editing.sortOrder,
          isEnabled: editing.isEnabled,
        })
      } else {
        form.resetFields()
        form.setFieldsValue({
          marketCategory: 'A股',
          dataSource: 'sina',
          sortOrder: 100,
          isEnabled: false,
        })
      }
    }
  }, [open, editing, form])

  const handleOk = async () => {
    const values = await form.validateFields()
    onSubmit(values)
  }

  return (
    <Modal
      title={editing ? '编辑跟踪指数' : '新增跟踪指数'}
      open={open}
      onOk={handleOk}
      onCancel={onCancel}
      confirmLoading={loading}
      destroyOnClose
    >
      <Form form={form} layout="vertical" autoComplete="off">
        <Form.Item
          label="指数代码"
          name="indexCode"
          rules={[{ required: true, message: '请输入指数代码' }]}
          extra={editing ? '指数代码创建后不可修改' : '如 sh000001 / GC00Y / US10Y'}
        >
          <Input placeholder="sh000001" disabled={!!editing} />
        </Form.Item>

        <Form.Item
          label="指数名称"
          name="indexName"
          rules={[{ required: true, message: '请输入指数名称' }]}
        >
          <Input placeholder="上证指数" />
        </Form.Item>

        <Form.Item
          label="市场类别"
          name="marketCategory"
          rules={[{ required: true, message: '请选择市场类别' }]}
        >
          <Select options={CATEGORY_OPTIONS} />
        </Form.Item>

        <Form.Item
          label="数据源"
          name="dataSource"
          rules={[{ required: true, message: '请选择数据源' }]}
          extra="启用校验：A股仅支持 sina；全球需在常量表中且数据源匹配"
        >
          <Select options={SOURCE_OPTIONS} />
        </Form.Item>

        <Form.Item label="排序" name="sortOrder">
          <InputNumber min={0} className="!w-full" />
        </Form.Item>

        <Form.Item
          label="启用"
          name="isEnabled"
          valuePropName="checked"
          extra="启用时校验数据源可用性，校验失败将返回 400"
        >
          <Switch />
        </Form.Item>
      </Form>
    </Modal>
  )
}
