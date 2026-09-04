import { Card, Form, Table } from 'antd'
import { useState } from 'react'

import { useHotspot } from '@/hooks/useHotspot'
import type { SectorFundFlow } from '@ai-invest/shared'
import { useColorScheme } from '@/stores/settings'

import { HotspotFilters, type FilterForm } from './components/HotspotFilters'
import { columns } from './utils'

export function Hotspot() {
  useColorScheme()
  const [form] = Form.useForm<FilterForm>()
  const [params, setParams] = useState({
    sectorType: '',
    tradeDate: '',
    page: 1,
    pageSize: 20,
  })

  const { data, isLoading } = useHotspot(params)

  const handleSearch = (values: FilterForm) => {
    setParams({
      sectorType: values.sectorType || '',
      tradeDate: values.tradeDate ? values.tradeDate.format('YYYY-MM-DD') : '',
      page: 1,
      pageSize: params.pageSize,
    })
  }

  return (
    <Card title="热点追踪" variant="borderless">
      <HotspotFilters form={form} onSearch={handleSearch} />

      <Table
        dataSource={data?.items || []}
        columns={columns}
        rowKey={(record: SectorFundFlow) => `${record.sectorCode}-${record.sectorType}-${record.tradeDate}`}
        loading={isLoading}
        pagination={{
          current: data?.page,
          pageSize: data?.pageSize,
          total: data?.total,
          onChange: (page, pageSize) => setParams((prev) => ({ ...prev, page, pageSize })),
        }}
      />
    </Card>
  )
}
