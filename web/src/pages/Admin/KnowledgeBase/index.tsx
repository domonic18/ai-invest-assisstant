import { Card, Tabs, Typography } from 'antd'
import { useSearchParams } from 'react-router-dom'

import { IngestTab } from './IngestTab'
import { ReviewTab } from './ReviewTab'
import { SettingsTab } from './SettingsTab'
import { SourcesTab } from './SourcesTab'

const TAB_KEYS = ['settings', 'sources', 'ingest', 'review'] as const

type TabKey = (typeof TAB_KEYS)[number]

export default function KnowledgeBase() {
  const [params, setParams] = useSearchParams()
  const activeKey = (TAB_KEYS as readonly string[]).includes(params.get('tab') ?? '')
    ? (params.get('tab') as TabKey)
    : 'settings'
  const sourceIdParam = params.get('sourceId')
  const sourceId = sourceIdParam ? Number(sourceIdParam) : null

  const navigate = (tab: TabKey, nextSourceId: number | null) => {
    const next: Record<string, string> = { tab }
    if (nextSourceId != null) next.sourceId = String(nextSourceId)
    setParams(next, { replace: true })
  }

  return (
    <div className="p-6">
      <Typography.Title level={4}>知识库管理</Typography.Title>
      <Card variant="borderless">
        <Tabs
          activeKey={activeKey}
          onChange={(key) => navigate(key as TabKey, sourceId)}
          items={[
            { key: 'settings', label: '知识库设置', children: <SettingsTab /> },
            {
              key: 'sources',
              label: '知识库列表',
              children: <SourcesTab onOpenIngest={(id) => navigate('ingest', id)} />,
            },
            {
              key: 'ingest',
              label: '素材接入',
              children: (
                <IngestTab
                  sourceId={sourceId}
                  onSourceChange={(id) => navigate('ingest', id)}
                />
              ),
            },
            {
              key: 'review',
              label: '知识审核',
              children: (
                <ReviewTab
                  sourceId={sourceId}
                  onSourceChange={(id) => navigate('review', id)}
                />
              ),
            },
          ]}
        />
      </Card>
    </div>
  )
}
