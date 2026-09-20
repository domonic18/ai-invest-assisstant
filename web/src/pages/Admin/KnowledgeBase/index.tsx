import { Card, Tabs, Typography } from 'antd'
import { useSearchParams } from 'react-router-dom'

import { ImagesTab } from './ImagesTab'
import { IngestTab } from './IngestTab'
import { ReviewTab } from './ReviewTab'
import { SearchTab } from './SearchTab'
import { SettingsTab } from './SettingsTab'
import { SourcesTab } from './SourcesTab'

const TAB_KEYS = ['settings', 'sources', 'ingest', 'review', 'images', 'search'] as const

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
            {
              key: 'images',
              label: '图片资产',
              children: (
                <ImagesTab
                  sourceId={sourceId}
                  onSourceChange={(id) => navigate('images', id)}
                />
              ),
            },
            {
              key: 'search',
              label: '知识检索',
              children: (
                <SearchTab
                  sourceId={sourceId}
                  onSourceChange={(id) => navigate('search', id)}
                />
              ),
            },
          ]}
        />
      </Card>
    </div>
  )
}
