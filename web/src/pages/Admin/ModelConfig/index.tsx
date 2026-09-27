import { Card, Tabs, Typography } from 'antd'
import { useSearchParams } from 'react-router-dom'

import { AsrTab } from './AsrTab'
import { KbBindingTab } from './KbBindingTab'
import { ModelsTab } from './ModelsTab'

const TAB_KEYS = ['models', 'asr', 'binding'] as const

type TabKey = (typeof TAB_KEYS)[number]

const TAB_LABELS: Record<TabKey, string> = {
  models: '模型条目',
  asr: 'ASR 渠道',
  binding: '知识库绑定',
}

export default function ModelConfig() {
  const [params, setParams] = useSearchParams()
  const activeKey = (TAB_KEYS as readonly string[]).includes(params.get('tab') ?? '')
    ? (params.get('tab') as TabKey)
    : 'models'

  return (
    <div className="p-6">
      <Typography.Title level={4}>模型配置</Typography.Title>
      <Card variant="borderless">
        <Tabs
          activeKey={activeKey}
          onChange={(key) => setParams({ tab: key }, { replace: true })}
          items={TAB_KEYS.map((key) => ({
            key,
            label: TAB_LABELS[key],
            children:
              key === 'models' ? <ModelsTab /> : key === 'asr' ? <AsrTab /> : <KbBindingTab />,
          }))}
        />
      </Card>
    </div>
  )
}
