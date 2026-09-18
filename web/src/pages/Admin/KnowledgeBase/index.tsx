import { Card, Tabs, Typography } from 'antd'
import { useSearchParams } from 'react-router-dom'

import { SettingsTab } from './SettingsTab'

const TAB_KEYS = ['settings'] as const

type TabKey = (typeof TAB_KEYS)[number]

const TAB_ITEMS = [
  {
    key: 'settings',
    label: '知识库设置',
    children: <SettingsTab />,
  },
]

export default function KnowledgeBase() {
  const [params, setParams] = useSearchParams()
  const activeKey = (TAB_KEYS as readonly string[]).includes(params.get('tab') ?? '')
    ? (params.get('tab') as TabKey)
    : 'settings'

  return (
    <div className="p-6">
      <Typography.Title level={4}>知识库管理</Typography.Title>
      <Card variant="borderless">
        <Tabs
          activeKey={activeKey}
          onChange={(key) => setParams({ tab: key }, { replace: true })}
          items={TAB_ITEMS}
        />
      </Card>
    </div>
  )
}
