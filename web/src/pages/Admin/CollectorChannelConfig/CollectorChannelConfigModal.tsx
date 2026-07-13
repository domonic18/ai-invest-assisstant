import { Checkbox, Form, Input, Modal, Select, Switch } from 'antd'
import { useEffect } from 'react'

import type {
  CollectorChannelConfig,
  CollectorChannelConfigFormValues,
  CollectorTaskName,
} from '@ai-invest/shared'

interface CollectorChannelConfigModalProps {
  open: boolean
  editing: CollectorChannelConfig | null
  onCancel: () => void
  onSubmit: (values: CollectorChannelConfigFormValues) => void
  loading: boolean
}

const SOURCE_OPTIONS = [
  { value: 'sina', label: '新浪财经' },
  { value: 'eastmoney', label: '东方财富' },
  { value: 'ths', label: '同花顺' },
  { value: 'cninfo', label: '巨潮资讯' },
]

const DATA_TYPE_OPTIONS: { value: CollectorTaskName; label: string }[] = [
  { value: 'kline', label: 'K 线' },
  { value: 'auction', label: '集合竞价' },
  { value: 'fund-flow', label: '资金流向' },
  { value: 'news', label: '新闻' },
  { value: 'company-profile', label: '公司概况' },
  { value: 'disclosure', label: '公告披露' },
  { value: 'sector-fund-flow', label: '板块资金流向' },
  { value: 'dragon-list', label: '龙虎榜' },
  { value: 'research-report', label: '个股研报' },
  { value: 'macro', label: '宏观经济' },
]

export function CollectorChannelConfigModal({
  open,
  editing,
  onCancel,
  onSubmit,
  loading,
}: CollectorChannelConfigModalProps) {
  const [form] = Form.useForm<CollectorChannelConfigFormValues>()

  useEffect(() => {
    if (open) {
      if (editing) {
        form.setFieldsValue({
          source: editing.source,
          name: editing.name,
          baseUrl: editing.baseUrl || '',
          apiKey: '',
          isEnabled: editing.isEnabled,
          supportedDataTypes: editing.supportedDataTypes,
        })
      } else {
        form.resetFields()
        form.setFieldsValue({
          source: 'sina',
          isEnabled: true,
          supportedDataTypes: ['kline', 'auction'],
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
      title={editing ? '编辑采集渠道' : '新增采集渠道'}
      open={open}
      onOk={handleOk}
      onCancel={onCancel}
      confirmLoading={loading}
      destroyOnClose
    >
      <Form form={form} layout="vertical" autoComplete="off">
        <Form.Item
          label="渠道标识"
          name="source"
          rules={[{ required: true, message: '请选择渠道标识' }]}
        >
          <Select
            options={SOURCE_OPTIONS}
            disabled={!!editing}
            placeholder="如 sina / eastmoney / ths"
          />
        </Form.Item>

        <Form.Item
          label="名称"
          name="name"
          rules={[{ required: true, message: '请输入渠道名称' }]}
        >
          <Input placeholder="如：新浪财经公开行情" />
        </Form.Item>

        <Form.Item label="API 地址" name="baseUrl">
          <Input placeholder="https://hq.sinajs.cn（可选）" />
        </Form.Item>

        <Form.Item label="API Key" name="apiKey">
          <Input.Password
            placeholder={editing ? '留空表示不修改' : '渠道 API Key（可选）'}
          />
        </Form.Item>

        <Form.Item
          label="支持的数据类型"
          name="supportedDataTypes"
          rules={[{ required: true, message: '请至少选择一种数据类型' }]}
        >
          <Checkbox.Group options={DATA_TYPE_OPTIONS} />
        </Form.Item>

        <Form.Item label="启用" name="isEnabled" valuePropName="checked">
          <Switch />
        </Form.Item>
      </Form>
    </Modal>
  )
}
