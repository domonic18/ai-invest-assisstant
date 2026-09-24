import { ApiOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { App, Button, Card, Form, Input, Popconfirm, Select, Tag } from 'antd'
import { useEffect, useState } from 'react'
import type { ApiUserLlmConfigUpsertRequest } from '@ai-invest/shared'

import { testMyLlmConfig } from '@/api/account'
import { useClearMyLlmConfig, useMyLlmConfig, useSaveMyLlmConfig } from '@/hooks/useAccount'

interface MyModelFormValues {
  protocol: 'openai' | 'anthropic'
  baseUrl: string
  modelName: string
  apiKey: string
}

const PROTOCOL_OPTIONS = [
  { value: 'openai', label: 'OpenAI 兼容（DeepSeek / 智谱 / Minimax 等）' },
  { value: 'anthropic', label: 'Anthropic 协议（Claude / Kimi coding 等）' },
]

export function MyModelSection() {
  const { message } = App.useApp()
  const configQ = useMyLlmConfig()
  const saveMutation = useSaveMyLlmConfig()
  const clearMutation = useClearMyLlmConfig()
  const [form] = Form.useForm<MyModelFormValues>()
  const [testing, setTesting] = useState(false)
  const [editing, setEditing] = useState(false)

  const config = configQ.data ?? null

  useEffect(() => {
    if (config && !editing) {
      form.setFieldsValue({
        protocol: config.protocol,
        baseUrl: config.baseUrl,
        modelName: config.modelName,
        apiKey: '',
      })
    } else if (!config) {
      form.resetFields()
      form.setFieldsValue({ protocol: 'openai' })
    }
  }, [config, editing, form])

  const collectDraft = async (): Promise<ApiUserLlmConfigUpsertRequest | null> => {
    const values = await form.validateFields()
    return {
      protocol: values.protocol,
      baseUrl: values.baseUrl.trim(),
      modelName: values.modelName.trim(),
      apiKey: values.apiKey.trim(),
    }
  }

  const handleTest = async () => {
    const draft = await collectDraft()
    if (!draft) return
    setTesting(true)
    try {
      const result = await testMyLlmConfig(draft)
      if (result.status === 'success') {
        message.success(result.detail || '连接正常')
      } else {
        message.error(result.detail || '连接失败，请检查配置')
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : '测试请求失败')
    } finally {
      setTesting(false)
    }
  }

  const handleSave = async () => {
    const draft = await collectDraft()
    if (!draft) return
    try {
      await saveMutation.mutateAsync(draft)
      message.success('自备模型已启用：此后 AI 功能全部走自有 Key，不占配额')
      setEditing(false)
    } catch (error) {
      message.error(error instanceof Error ? error.message : '保存失败')
    }
  }

  const handleClear = async () => {
    try {
      await clearMutation.mutateAsync()
      message.success('已清除自备模型，回落系统模型（此后受配额约束）')
      setEditing(false)
    } catch (error) {
      message.error(error instanceof Error ? error.message : '清除失败')
    }
  }

  const startEdit = () => {
    setEditing(true)
    if (config) {
      form.setFieldsValue({ apiKey: '' })
    }
  }

  return (
    <Card
      variant="borderless"
      title="我的模型（自备 API Key）"
      extra={
        config ? (
          <Tag bordered={false} color="green">已启用</Tag>
        ) : (
          <Tag bordered={false}>未配置</Tag>
        )
      }
    >
      {config && !editing ? (
        <div className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-2 text-xs">
            <DescItem label="协议" value={config.protocol === 'anthropic' ? 'Anthropic' : 'OpenAI 兼容'} />
            <DescItem label="模型" value={config.modelName} />
            <DescItem label="Base URL" value={config.baseUrl} />
            <DescItem label="API Key" value={config.apiKeyMasked} mono />
          </div>
          <div className="flex gap-2">
            <Button size="small" onClick={startEdit}>
              修改配置
            </Button>
            <Popconfirm
              title="清除自备模型？"
              description="清除后立即回落系统模型，AI 调用将占用配额。"
              okText="清除"
              cancelText="取消"
              onConfirm={handleClear}
            >
              <Button size="small" danger loading={clearMutation.isPending}>
                清除
              </Button>
            </Popconfirm>
          </div>
        </div>
      ) : (
        <Form form={form} layout="vertical" className="max-w-lg">
          <Form.Item
            name="protocol"
            label="协议"
            rules={[{ required: true, message: '请选择协议' }]}
          >
            <Select options={PROTOCOL_OPTIONS} />
          </Form.Item>
          <Form.Item
            name="baseUrl"
            label="Base URL"
            rules={[
              { required: true, message: '请输入 Base URL' },
              { type: 'url', message: '请输入合法 URL（含 https://）' },
            ]}
          >
            <Input placeholder="https://api.example.com/v1" />
          </Form.Item>
          <Form.Item
            name="modelName"
            label="模型名"
            rules={[{ required: true, message: '请输入模型名' }]}
          >
            <Input placeholder="deepseek-chat / kimi-k2 ..." />
          </Form.Item>
          <Form.Item
            name="apiKey"
            label={config ? 'API Key（留空保持不变）' : 'API Key'}
            rules={
              editing && config
                ? []
                : [{ required: true, message: '请输入 API Key' }]
            }
            extra="仅用于本人 AI 调用；Fernet 加密存储、脱敏展示，不会出现在日志中"
          >
            <Input.Password placeholder={config ? '••••（已配置，输入以更换）' : 'sk-...'} />
          </Form.Item>
          <div className="flex gap-2 justify-end">
            {editing && config && (
              <Button onClick={() => setEditing(false)}>取消</Button>
            )}
            <Button icon={<ThunderboltOutlined />} loading={testing} onClick={handleTest}>
              连通性测试
            </Button>
            <Button
              type="primary"
              icon={<ApiOutlined />}
              loading={saveMutation.isPending}
              onClick={handleSave}
            >
              保存并启用
            </Button>
          </div>
        </Form>
      )}

      <div className="mt-3 rounded-md bg-[#181a21] border border-[#23262d] px-2.5 py-2 text-[11px] leading-relaxed text-[#8a8f98]">
        配置生效后，<b>助手对话、页面 AI 生成</b>等全部 AI 功能走自有 Key（不占配额、不计系统成本）；
        调用失败（无效 / 欠费 / 限流）<b>不回退系统模型</b>，直接报错请检查配置。建议保存前先做连通性测试。
      </div>
    </Card>
  )
}

function DescItem({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1 border-b border-[#1c1f26]">
      <span className="text-[#5c616e] shrink-0">{label}</span>
      <span className={`text-[#c9cdd4] truncate ${mono ? 'font-mono' : ''}`}>{value}</span>
    </div>
  )
}
