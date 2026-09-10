import { Card, Tabs } from 'antd'

import { NewsDocPanel } from './NewsDocPanel'
import { TelegraphPanel } from './TelegraphPanel'

export function AdminNews() {
  return (
    <Card title="资讯管理" variant="borderless">
      <Tabs
        items={[
          { key: 'telegraph', label: '电报', children: <TelegraphPanel /> },
          { key: 'news', label: '快讯', children: <NewsDocPanel docType="news" /> },
          {
            key: 'announcement',
            label: '公告',
            children: <NewsDocPanel docType="announcement" />,
          },
        ]}
      />
    </Card>
  )
}
