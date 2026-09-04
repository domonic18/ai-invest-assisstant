import { ReloadOutlined } from '@ant-design/icons'
import { Button, Card, Form, Table, Typography } from 'antd'
import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { useHotspot } from '@/hooks/useHotspot'
import { useTelegraph } from '@/hooks/useTelegraph'
import type { SectorFundFlow } from '@ai-invest/shared'
import { useColorScheme } from '@/stores/settings'

import { FundSignalCard } from './components/FundSignalCard'
import { HotTimeline } from './components/HotTimeline'
import { HotspotFilters, type FilterForm } from './components/HotspotFilters'
import { columns } from './utils'

export function Hotspot() {
  useColorScheme()
  const queryClient = useQueryClient()
  const [form] = Form.useForm<FilterForm>()
  const [params, setParams] = useState({
    sectorType: '',
    tradeDate: '',
    page: 1,
    pageSize: 20,
  })

  const { data, isLoading } = useHotspot(params)
  const { data: telegraph, isLoading: telegraphLoading } = useTelegraph(1, 15, undefined, true)

  const handleSearch = (values: FilterForm) => {
    setParams({
      sectorType: values.sectorType || '',
      tradeDate: values.tradeDate ? values.tradeDate.format('YYYY-MM-DD') : '',
      page: 1,
      pageSize: params.pageSize,
    })
  }

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ['hotspot'] })
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Typography.Title level={4} className="!mb-0">
          热点追踪
        </Typography.Title>
        <div className="flex items-center gap-3">
          <span className="hidden md:inline text-xs text-gray-400">
            电报 10s 准实时 · 板块数据 5 分钟自动刷新
          </span>
          <Button size="small" icon={<ReloadOutlined />} onClick={handleRefresh}>
            手动刷新
          </Button>
        </div>
      </div>

      {/* 原型 grid-2-1 双栏：左实时热点时间线，右资金异动信号 */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <Card
          title="实时热点时间线"
          variant="borderless"
          className="xl:col-span-2"
          extra={<Link to="/telegraph" className="text-xs">更多电报</Link>}
        >
          <HotTimeline items={telegraph?.items} loading={telegraphLoading} />
        </Card>
        <Card title="资金异动信号" variant="borderless">
          <FundSignalCard />
        </Card>
      </div>

      <Card title="板块资金明细" variant="borderless">
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
    </div>
  )
}
