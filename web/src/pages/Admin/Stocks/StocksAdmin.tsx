/**
 * 股票与题材管理：股票台账 / 题材（股票-概念）映射 双 tab 合一（tab 与 ?tab= 同步，
 * 范式同采集管理 CollectorAdmin）；旧路由 /admin/stock-concepts 重定向到 concepts tab。
 */
import { Tabs } from 'antd'
import { useSearchParams } from 'react-router-dom'

import { StockConcepts } from '../StockConcepts/StockConcepts'

import { AdminStocks } from './Stocks'

const TAB_KEYS = ['stocks', 'concepts'] as const
type TabKey = (typeof TAB_KEYS)[number]

function resolveTab(raw: string | null): TabKey {
  return (TAB_KEYS as readonly string[]).includes(raw ?? '') ? (raw as TabKey) : 'stocks'
}

export function StocksAdmin() {
  const [searchParams, setSearchParams] = useSearchParams()
  const activeKey = resolveTab(searchParams.get('tab'))

  return (
    <Tabs
      activeKey={activeKey}
      onChange={(key) => setSearchParams({ tab: key }, { replace: true })}
      items={[
        { key: 'stocks', label: '股票管理', children: <AdminStocks /> },
        { key: 'concepts', label: '题材映射', children: <StockConcepts /> },
      ]}
    />
  )
}
