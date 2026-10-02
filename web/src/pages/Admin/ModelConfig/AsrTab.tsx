import { SoundOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Descriptions, Spin, Tag, message } from 'antd'
import { useState } from 'react'
import { ASR_PROVIDER_PRESETS } from '@ai-invest/shared'
import type { ApiAsrConfigUpdateRequest } from '@ai-invest/shared'

import { useAsrConfig, useUpdateAsrConfig } from '@/hooks/useModelConfig'

import { AsrConfigModal } from './AsrConfigModal'

const PROTOCOL_LABEL: Record<string, string> = {
  minimax: 'MiniMax 专有',
  openai: 'OpenAI 兼容',
}

export function AsrTab() {
  const { data: config, isLoading } = useAsrConfig()
  const updateMutation = useUpdateAsrConfig()
  const [modalOpen, setModalOpen] = useState(false)

  const handleSave = async (values: ApiAsrConfigUpdateRequest) => {
    try {
      await updateMutation.mutateAsync(values)
      message.success('ASR 配置已保存，即刻生效')
      setModalOpen(false)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '保存失败')
    }
  }

  return (
    <Card
      title="ASR 转写渠道"
      variant="borderless"
      extra={
        <Button
          type="primary"
          icon={<SoundOutlined />}
          disabled={isLoading}
          onClick={() => setModalOpen(true)}
        >
          编辑配置
        </Button>
      }
    >
      <Alert
        type="info"
        showIcon
        className="mb-4"
        message="语音转文字渠道：社媒内容判断与知识库音视频转写共用此配置，支持 MiniMax / OpenAI 兼容（硅基流动、Groq、本地部署等），保存后即刻生效"
      />
      {isLoading || !config ? (
        <Spin />
      ) : (
        <Descriptions
          column={2}
          bordered
          size="small"
          items={[
            {
              key: 'provider',
              label: '供应商',
              children:
                ASR_PROVIDER_PRESETS[config.provider]?.label ??
                (config.provider === 'custom' ? '自定义' : config.provider),
            },
            {
              key: 'protocol',
              label: '调用协议',
              children: PROTOCOL_LABEL[config.protocol] ?? config.protocol,
            },
            { key: 'model', label: '模型', children: config.model },
            { key: 'baseUrl', label: 'Base URL', children: config.baseUrl },
            {
              key: 'apiKey',
              label: 'API Key',
              children: config.apiKeyConfigured
                ? `已配置（${config.apiKeyMasked ?? '****'}）`
                : '未配置',
            },
            {
              key: 'maxAudioSeconds',
              label: '单条音频时长上限',
              children: `${config.maxAudioSeconds} 秒`,
            },
            { key: 'hotwords', label: '热词数', children: config.hotwords.length },
            {
              key: 'enabled',
              label: '状态',
              children: config.enabled ? (
                <Tag color="green">启用</Tag>
              ) : (
                <Tag color="default">已关闭</Tag>
              ),
            },
          ]}
        />
      )}

      <AsrConfigModal
        open={modalOpen}
        config={config ?? null}
        loading={updateMutation.isPending}
        onCancel={() => setModalOpen(false)}
        onSubmit={handleSave}
      />
    </Card>
  )
}
