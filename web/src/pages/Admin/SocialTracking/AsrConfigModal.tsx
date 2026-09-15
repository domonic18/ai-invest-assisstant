import { SoundOutlined } from '@ant-design/icons'
import { Alert, Button, Form, Input, InputNumber, Modal, Space, Switch, Typography } from 'antd'
import { useEffect, useState } from 'react'
import type { ApiAsrConfig, ApiAsrConfigTestResult } from '@ai-invest/shared'

import { useTestAsrConfig } from '@/hooks/useAdminSocial'

interface AsrConfigModalProps {
  open: boolean
  config: ApiAsrConfig | null
  loading: boolean
  onCancel: () => void
  onSubmit: (values: {
    baseUrl?: string
    model?: string
    apiKey?: string
    maxAudioSeconds?: number
    hotwords?: string[]
    enabled?: boolean
  }) => void
}

interface AsrFormValues {
  baseUrl: string
  model: string
  apiKey?: string
  maxAudioSeconds: number
  hotwordsText?: string
  enabled: boolean
}

export function AsrConfigModal({
  open,
  config,
  loading,
  onCancel,
  onSubmit,
}: AsrConfigModalProps) {
  const [form] = Form.useForm<AsrFormValues>()
  const [testResult, setTestResult] = useState<ApiAsrConfigTestResult | null>(null)
  const testMutation = useTestAsrConfig()

  useEffect(() => {
    if (!open) return
    setTestResult(null)
    form.resetFields()
    if (config) {
      form.setFieldsValue({
        baseUrl: config.baseUrl,
        model: config.model,
        maxAudioSeconds: config.maxAudioSeconds,
        hotwordsText: config.hotwords.join('\n'),
        enabled: config.enabled,
      })
    }
  }, [open, config, form])

  const handleTest = async () => {
    setTestResult(null)
    try {
      setTestResult(await testMutation.mutateAsync())
    } catch (err) {
      setTestResult({
        ok: false,
        latencyMs: 0,
        text: null,
        error: err instanceof Error ? err.message : '测试请求失败',
      })
    }
  }

  return (
    <Modal
      title="ASR 转写配置"
      open={open}
      onCancel={onCancel}
      destroyOnHidden
      width={640}
      footer={[
        <Button key="cancel" onClick={onCancel}>
          取消
        </Button>,
        <Button
          key="test"
          icon={<SoundOutlined />}
          loading={testMutation.isPending}
          onClick={handleTest}
        >
          测试连接
        </Button>,
        <Button key="submit" type="primary" loading={loading} onClick={() => form.submit()}>
          保存
        </Button>,
      ]}
    >
      <Form
        form={form}
        layout="vertical"
        onFinish={(values) =>
          onSubmit({
            baseUrl: values.baseUrl,
            model: values.model,
            apiKey: values.apiKey || undefined,
            maxAudioSeconds: values.maxAudioSeconds,
            hotwords: (values.hotwordsText ?? '')
              .split('\n')
              .map((w) => w.trim())
              .filter(Boolean),
            enabled: values.enabled,
          })
        }
      >
        <Space align="baseline" className="w-full">
          <Form.Item
            name="baseUrl"
            label="Base URL"
            rules={[{ required: true, message: '请输入服务 Base URL' }]}
          >
            <Input placeholder="https://api.minimaxi.com" style={{ width: 320 }} />
          </Form.Item>
          <Form.Item
            name="model"
            label="模型"
            rules={[{ required: true, message: '请输入模型名' }]}
          >
            <Input placeholder="如 asr-1.0" style={{ width: 160 }} />
          </Form.Item>
        </Space>
        <Form.Item
          name="apiKey"
          label="API Key"
          extra={
            config?.apiKeyConfigured
              ? `已配置（${config.apiKeyMasked ?? '****'}），留空保留原值`
              : '首次使用请填写'
          }
        >
          <Input.Password placeholder={config?.apiKeyConfigured ? '留空保留原值' : 'sk-...'} autoComplete="new-password" />
        </Form.Item>
        <Form.Item
          name="maxAudioSeconds"
          label="单条音频时长上限（秒）"
          rules={[{ required: true, message: '请输入时长上限' }]}
          extra="超上限的音频直接降级为未转写，不阻塞内容入库"
        >
          <InputNumber min={30} max={3600} style={{ width: 160 }} />
        </Form.Item>
        <Form.Item
          name="hotwordsText"
          label="热词表（每行一个）"
          extra="官方接口无热词参数；热词注入情绪判断 prompt 纠偏口播术语"
        >
          <Input.TextArea rows={3} placeholder={'美联储\n北向资金\n集合竞价'} />
        </Form.Item>
        <Form.Item name="enabled" label="启用转写" valuePropName="checked">
          <Switch />
        </Form.Item>
        <Alert
          type="info"
          showIcon
          message="关闭后采集侧直接降级为未转写（判断仅基于标题/文案），历史文稿不受影响"
        />
        {testResult && (
          <Alert
            className="mt-3"
            type={testResult.ok ? 'success' : 'error'}
            showIcon
            message={
              testResult.ok
                ? `连接正常（${testResult.latencyMs}ms），样例转写：${testResult.text ?? '-'}`
                : `连接失败（${testResult.latencyMs}ms）`
            }
            description={testResult.ok ? undefined : testResult.error ?? '未知错误'}
          />
        )}
        <Typography.Paragraph type="secondary" className="!mb-0 mt-3">
          保存后即刻生效：采集任务在转写时读取此配置，无需重启服务。
        </Typography.Paragraph>
      </Form>
    </Modal>
  )
}
