import { Form, Input, Modal, Select, Switch } from 'antd'
import { useEffect } from 'react'

import type { LLMConfig, LLMConfigFormValues } from '@ai-invest/shared'

interface LLMConfigModalProps {
  open: boolean
  editing: LLMConfig | null
  onCancel: () => void
  onSubmit: (values: LLMConfigFormValues) => void
  loading: boolean
}

const PROVIDER_OPTIONS = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'zhipu', label: '智谱 GLM' },
  { value: 'custom', label: '自定义' },
]

export function LLMConfigModal({ open, editing, onCancel, onSubmit, loading }: LLMConfigModalProps) {
  const [form] = Form.useForm<LLMConfigFormValues>()

  useEffect(() => {
    if (open) {
      const capabilities = (editing?.extra?.capabilities ?? {}) as { vision?: boolean }
      if (editing) {
        form.setFieldsValue({
          name: editing.name,
          provider: editing.provider,
          baseUrl: editing.baseUrl,
          modelName: editing.modelName,
          apiKey: '',
          isDefault: editing.isDefault,
          isActive: editing.isActive,
          vision: capabilities.vision === true,
        })
      } else {
        form.resetFields()
        form.setFieldsValue({
          provider: 'openai',
          isActive: true,
          isDefault: false,
          vision: false,
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
      title={editing ? '编辑模型配置' : '新增模型配置'}
      open={open}
      onOk={handleOk}
      onCancel={onCancel}
      confirmLoading={loading}
      destroyOnClose
    >
      <Form form={form} layout="vertical" autoComplete="off">
        <Form.Item
          label="名称"
          name="name"
          rules={[{ required: true, message: '请输入名称' }]}
        >
          <Input placeholder="如：OpenAI GPT-4o" />
        </Form.Item>

        <Form.Item
          label="供应商"
          name="provider"
          rules={[{ required: true, message: '请选择供应商' }]}
        >
          <Select options={PROVIDER_OPTIONS} />
        </Form.Item>

        <Form.Item
          label="API 地址 (Base URL)"
          name="baseUrl"
          rules={[{ required: true, message: '请输入 API 地址' }]}
        >
          <Input placeholder="https://api.openai.com/v1" />
        </Form.Item>

        <Form.Item
          label="模型名称"
          name="modelName"
          rules={[{ required: true, message: '请输入模型名称' }]}
        >
          <Input placeholder="gpt-4o" />
        </Form.Item>

        <Form.Item
          label="API Key"
          name="apiKey"
          rules={[{ required: !editing, message: '请输入 API Key' }]}
        >
          <Input.Password placeholder={editing ? '留空表示不修改' : 'sk-...'} />
        </Form.Item>

        <Form.Item label="设为默认" name="isDefault" valuePropName="checked">
          <Switch />
        </Form.Item>

        <Form.Item label="启用" name="isActive" valuePropName="checked">
          <Switch />
        </Form.Item>

        <Form.Item
          label="视觉能力"
          name="vision"
          valuePropName="checked"
          extra="开启后该模型可用于图片识别（如自选股截图导入），须为支持图片输入的模型"
        >
          <Switch />
        </Form.Item>
      </Form>
    </Modal>
  )
}
