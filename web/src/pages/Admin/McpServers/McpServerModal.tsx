import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons'
import {
  Alert,
  Button,
  Collapse,
  Form,
  Input,
  InputNumber,
  Modal,
  Segmented,
  Space,
  Switch,
} from 'antd'
import { useEffect, useState } from 'react'
import type { ApiMcpServerConfig, McpTransportType } from '@ai-invest/shared'

import type { McpServerFormValues, McpServerPayload } from './mcpServerForm'
import { parseMcpConfigJson, toPayload } from './mcpServerForm'

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
  const [importText, setImportText] = useState('')
  const [importResult, setImportResult] = useState<{ ok: boolean; message: string } | null>(null)

  useEffect(() => {
    if (!open) return
    form.resetFields()
    setImportText('')
    setImportResult(null)
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

  const handleImportJson = () => {
    try {
      const cfg = parseMcpConfigJson(importText)
      const toPairs = (record: Record<string, string>) =>
        Object.entries(record).map(([key, value]) => ({ key, value }))
      form.setFieldsValue({
        ...(cfg.name !== undefined ? { name: cfg.name } : {}),
        transportType: cfg.transportType,
        ...(cfg.transportType === 'stdio'
          ? { command: cfg.command, args: cfg.args.join('\n'), env: toPairs(cfg.env) }
          : { url: cfg.url, headers: toPairs(cfg.headers) }),
      })
      setImportResult({ ok: true, message: '已解析并预填表单，可继续手动调整' })
    } catch (err) {
      setImportResult({
        ok: false,
        message: err instanceof Error ? err.message : '解析失败',
      })
    }
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
      <Collapse
        ghost
        size="small"
        className="mb-3 -ml-4"
        items={[
          {
            key: 'import',
            label: '从 JSON 配置导入（Claude Desktop / Cursor 格式）',
            children: (
              <div className="space-y-2">
                <Input.TextArea
                  rows={6}
                  value={importText}
                  onChange={(e) => setImportText(e.target.value)}
                  style={{ fontFamily: 'monospace' }}
                  placeholder={`{\n  "mcpServers": {\n    "squadsight": {\n      "url": "https://example.com/mcp",\n      "headers": {\n        "Authorization": "Bearer <YOUR_API_KEY>"\n      }\n    }\n  }\n}`}
                />
                <Button size="small" onClick={handleImportJson}>
                  解析并预填
                </Button>
                {importResult && (
                  <Alert
                    type={importResult.ok ? 'success' : 'error'}
                    showIcon
                    message={importResult.message}
                  />
                )}
              </div>
            ),
          },
        ]}
      />
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
              valuePlaceholder="如 Bearer <YOUR_API_KEY>"
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
          message="启用后工具将注入 AI 助手：保存/修改配置后助手自动重建并生效，工具调用时按需连接服务"
        />
      </Form>
    </Modal>
  )
}
