import { Tabs } from 'antd'
import { useSearchParams } from 'react-router-dom'

import { CollectorChannelConfig } from '../CollectorChannelConfig/CollectorChannelConfig'
import { AdminTasks } from '../Tasks/Tasks'
import { Collector } from './Collector'

const TAB_KEYS = ['run', 'tasks', 'channels'] as const
type TabKey = (typeof TAB_KEYS)[number]

function resolveTab(raw: string | null): TabKey {
  return (TAB_KEYS as readonly string[]).includes(raw ?? '') ? (raw as TabKey) : 'run'
}

/** 采集管理：执行与日志 / 任务配置 / 渠道配置 三合一（tab 与 ?tab= 同步，兼容旧路由重定向）。 */
export function CollectorAdmin() {
  const [searchParams, setSearchParams] = useSearchParams()
  const activeKey = resolveTab(searchParams.get('tab'))

  return (
    <Tabs
      activeKey={activeKey}
      onChange={(key) => setSearchParams({ tab: key }, { replace: true })}
      items={[
        { key: 'run', label: '执行与日志', children: <Collector /> },
        { key: 'tasks', label: '任务配置', children: <AdminTasks /> },
        { key: 'channels', label: '渠道配置', children: <CollectorChannelConfig /> },
      ]}
    />
  )
}
