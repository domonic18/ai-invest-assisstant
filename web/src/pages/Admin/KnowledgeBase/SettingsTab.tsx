import { Button, Card, Form, InputNumber, Select, Space, Switch, message } from 'antd'
import { useEffect } from 'react'

import type { ApiKbSettingsResponse } from '@ai-invest/shared'

import { useKbSettings, useUpdateKbSettings } from '@/hooks/useAdminKb'

interface KbSettingsFormValues {
  topK: number
  autoApprovePoints: boolean
  segmentMaxSeconds: number
  asrConcurrency: number
  hotwords: string[]
}

function toFormValues(settings: ApiKbSettingsResponse): KbSettingsFormValues {
  return {
    topK: settings.topK,
    autoApprovePoints: settings.autoApprovePoints,
    segmentMaxSeconds: settings.segmentMaxSeconds,
    asrConcurrency: settings.asrConcurrency,
    hotwords: settings.hotwords,
  }
}

export function SettingsTab() {
  const [form] = Form.useForm<KbSettingsFormValues>()
  const { data: settings, isLoading } = useKbSettings()
  const updateMutation = useUpdateKbSettings()

  useEffect(() => {
    if (settings) form.setFieldsValue(toFormValues(settings))
  }, [settings, form])

  const handleSave = async (values: KbSettingsFormValues) => {
    try {
      await updateMutation.mutateAsync(values)
      message.success('知识库设置已保存')
    } catch (err) {
      message.error(err instanceof Error ? err.message : '保存失败')
    }
  }

  return (
    <Form
      form={form}
      layout="vertical"
      onFinish={handleSave}
      disabled={isLoading}
      style={{ maxWidth: 640 }}
    >
      <Card
        type="inner"
        title="域参数"
        style={{ marginBottom: 16 }}
        extra={
          <Button type="primary" htmlType="submit" loading={updateMutation.isPending}>
            保存设置
          </Button>
        }
      >
        <Space wrap size="large">
          <Form.Item
            label="检索 top K"
            name="topK"
            rules={[{ required: true, message: '请输入' }]}
            extra="检索召回的知识片段数量"
          >
            <InputNumber min={1} max={50} style={{ width: 120 }} />
          </Form.Item>
          <Form.Item
            label="音频分段上限（秒）"
            name="segmentMaxSeconds"
            rules={[{ required: true, message: '请输入' }]}
            extra="ASR 单请求分段时长上限"
          >
            <InputNumber min={5} max={120} style={{ width: 120 }} />
          </Form.Item>
          <Form.Item
            label="ASR 并发数"
            name="asrConcurrency"
            rules={[{ required: true, message: '请输入' }]}
            extra="转写分片并发请求上限"
          >
            <InputNumber min={1} max={8} style={{ width: 120 }} />
          </Form.Item>
          <Form.Item
            label="全绿卡自动发布"
            name="autoApprovePoints"
            valuePropName="checked"
            extra="开启后抽取卡无升级理由（时间码/摘录/归章/置信度全过）时直接发布；关闭则全部进人工审核"
          >
            <Switch />
          </Form.Item>
        </Space>
        <Form.Item
          label="热词"
          name="hotwords"
          extra="转写与清洗时提升专有名词识别（回车添加）"
        >
          <Select mode="tags" open={false} placeholder="输入后回车添加" style={{ width: '100%' }} />
        </Form.Item>
      </Card>
    </Form>
  )
}
