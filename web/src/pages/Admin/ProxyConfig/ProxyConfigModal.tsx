import { Form, Input, InputNumber, Modal, Select, Switch } from 'antd'
import { useEffect } from 'react'

import type { ProxyConfig, ProxyConfigFormValues } from '@ai-invest/shared'

interface ProxyConfigModalProps {
  open: boolean
  editing: ProxyConfig | null
  onCancel: () => void
  onSubmit: (values: ProxyConfigFormValues) => void
  loading: boolean
}

const PROTOCOL_OPTIONS = [
  { value: 'http', label: 'HTTP' },
  { value: 'socks5', label: 'SOCKS5' },
]

export function ProxyConfigModal({ open, editing, onCancel, onSubmit, loading }: ProxyConfigModalProps) {
  const [form] = Form.useForm<ProxyConfigFormValues>()

  useEffect(() => {
    if (open) {
      if (editing) {
        form.setFieldsValue({
          name: editing.name,
          protocol: editing.protocol,
          host: editing.host,
          port: editing.port,
          username: editing.username ?? '',
          password: '',
          isEnabled: editing.isEnabled,
        })
      } else {
        form.resetFields()
        form.setFieldsValue({
          protocol: 'http',
          port: 7890,
          isEnabled: true,
        })
      }
    }
  }, [open, editing, form])

  const handleOk = async () => {
    // 校验失败（如密码必填）时静默返回，避免 Modal onOk 的 rejection 无人处理
    const values = await form.validateFields().catch(() => undefined)
    if (values) {
      onSubmit(values)
    }
  }

  return (
    <Modal
      title={editing ? '编辑代理服务器' : '新增代理服务器'}
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
          <Input placeholder="如：Mac mini Clash" />
        </Form.Item>

        <Form.Item
          label="协议"
          name="protocol"
          rules={[{ required: true, message: '请选择协议' }]}
        >
          <Select options={PROTOCOL_OPTIONS} />
        </Form.Item>

        <Form.Item
          label="主机"
          name="host"
          rules={[{ required: true, message: '请输入主机地址' }]}
        >
          <Input placeholder="175.27.167.123" />
        </Form.Item>

        <Form.Item
          label="端口"
          name="port"
          rules={[{ required: true, message: '请输入端口' }]}
        >
          <InputNumber min={1} max={65535} style={{ width: '100%' }} />
        </Form.Item>

        <Form.Item label="用户名" name="username">
          <Input placeholder="可选" autoComplete="off" />
        </Form.Item>

        <Form.Item label="密码" name="password">
          <Input.Password placeholder={editing ? '留空表示不修改' : '可选'} autoComplete="new-password" />
        </Form.Item>

        <Form.Item label="启用" name="isEnabled" valuePropName="checked">
          <Switch />
        </Form.Item>
      </Form>
    </Modal>
  )
}
