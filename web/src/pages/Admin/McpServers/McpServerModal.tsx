import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons'
import {
  Alert,
  Button,
  Form,
  Input,
  InputNumber,
  Modal,
  Segmented,
  Space,
  Switch,
} from 'antd'
import { useEffect } from 'react'
import type { ApiMcpServerConfig, McpTransportType } from '@ai-invest/shared'

import type { McpServerFormValues, McpServerPayload } from './mcpServerForm'
import { toPayload } from './mcpServerForm'

interface McpServerModalProps {
  open: boolean
  editing: ApiMcpServerConfig | null
  loading: boolean
  testing: boolean
  onCancel: () => void
  onSubmit: (values: McpServerPayload) => void
  onTestDraft: (values: McpServerPayload) => void
}

const TRANSPORT_OPTIONS: { label: string; value: McpTransportType }[] = [
  { label: 'HTTP (Streamable)', value: 'http' },
  { label: 'SSE', value: 'sse' },
  { label: 'stdio', value: 'stdio' },
]

function KvList({
  name,
  label,
  keyPlaceholder,
  valuePlaceholder,
}: {
  name: 'headers' | 'env'
  label: string
  keyPlaceholder: string
  valuePlaceholder: string
}) {
  return (
    <Form.Item label={label} required={false}>
      <Form.List name={name} initialValue={[]}>
        {(fields, { add, remove }) => (
          <>
            {fields.map((field) => (
              <Space key={field.key} align="baseline" className="mb-2 w-full">
                <Form.Item
                  name={[field.name, 'key']}
                  noStyle
                  rules={[{ required: false, message: '' }]}
                >
                  <Input placeholder={keyPlaceholder} style={{ width: 160 }} />
                </Form.Item>
                <Form.Item name={[field.name, 'value']} noStyle>
                  <Input placeholder={valuePlaceholder} style={{ width: 260 }} />
                </Form.Item>
                <MinusCircleOutlined onClick={() => remove(field.name)} />
              </Space>
            ))}
            <Button type="dashed" icon={<PlusOutlined />} onClick={() => add()} block>
              添加一项
            </Button>
          </>
        )}
      </Form.List>
    </Form.Item>
  )
}

export function McpServerModal({
  open,
  editing,
  loading,
  testing,
  onCancel,
  onSubmit,
  onTestDraft,
}: McpServerModalProps) {
  const [form] = Form.useForm<McpServerFormValues>()
  const transportType = Form.useWatch('transportType', form) ?? 'http'

  useEffect(() => {
    if (!open) return
    form.resetFields()
    if (editing) {
      const toPairs = (record: Record<string, string>) =>
        Object.entries(record).map(([key, value]) => ({ key, value }))
      form.setFieldsValue({
        name: editing.name,
        transportType: editing.transportType,
        command: editing.command ?? undefined,
        args: (editing.args ?? []).join('\n'),
        url: editing.url ?? undefined,
        headers: toPairs(editing.headers ?? {}),
        env: toPairs(editing.env ?? {}),
        enabled: editing.enabled,
        timeoutSeconds: editing.timeoutSeconds,
      })
    } else {
      form.setFieldsValue({
        transportType: 'http',
        enabled: false,
        timeoutSeconds: 30,
        args: '',
      })
    }
  }, [open, editing, form])

  const handleFinish = (values: McpServerFormValues) => {
    onSubmit(toPayload(values))
  }

  return (
    <Modal
      title={editing ? `编辑 MCP 服务：${editing.name}` : '新增 MCP 服务'}
      open={open}
      onCancel={onCancel}
      width={640}
      destroyOnHidden
      footer={[
        <Button key="cancel" onClick={onCancel}>
          取消
        </Button>,
        <Button
          key="test"
          icon={<span aria-hidden>🔌</span>}
          loading={testing}
          onClick={() => {
            form
              .validateFields()
              .then((values) => onTestDraft(toPayload(values)))
              .catch(() => undefined)
          }}
        >
          连接测试
        </Button>,
        <Button
          key="submit"
          type="primary"
          loading={loading}
          onClick={() => form.submit()}
        >
          保存
        </Button>,
      ]}
    >
      <Form form={form} layout="vertical" onFinish={handleFinish}>
        <Space align="baseline" className="w-full">
          <Form.Item
            name="name"
            label="名称"
            rules={[{ required: true, message: '请输入名称' }]}
          >
            <Input placeholder="如 finance-mcp" style={{ width: 220 }} />
          </Form.Item>
          <Form.Item name="transportType" label="传输通道">
            <Segmented options={TRANSPORT_OPTIONS} />
          </Form.Item>
        </Space>

        {transportType === 'stdio' ? (
          <>
            <Form.Item
              name="command"
              label="启动命令"
              rules={[{ required: true, message: 'stdio 传输必须填写启动命令' }]}
            >
              <Input placeholder="如 npx 或 /usr/bin/python" />
            </Form.Item>
            <Form.Item name="args" label="参数（每行一个）">
              <Input.TextArea rows={3} placeholder={'-y\n@modelcontextprotocol/server-finance'} />
            </Form.Item>
            <KvList
              name="env"
              label="环境变量"
              keyPlaceholder="变量名"
              valuePlaceholder="值"
            />
          </>
        ) : (
          <>
            <Form.Item
              name="url"
              label="服务 URL"
              rules={[
                { required: true, message: '请填写服务 URL' },
                { type: 'url', message: 'URL 格式不正确' },
              ]}
            >
              <Input placeholder="https://example.com/mcp" />
            </Form.Item>
            <KvList
              name="headers"
              label="请求头（如 Authorization）"
              keyPlaceholder="Header 名"
              valuePlaceholder="值"
            />
          </>
        )}

        <Space align="baseline">
          <Form.Item
            name="timeoutSeconds"
            label="超时（秒）"
            rules={[{ required: true, message: '请填写超时秒数' }]}
          >
            <InputNumber min={1} max={300} style={{ width: 120 }} />
          </Form.Item>
          <Form.Item name="enabled" label="启用注入" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Space>

        <Alert
          type="info"
          showIcon
          message="启用后工具清单将在助手重建时注入（当前为 Phase 2 接缝，保存即可生效配置）"
        />
      </Form>
    </Modal>
  )
}
