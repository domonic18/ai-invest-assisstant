import { ReloadOutlined } from '@ant-design/icons'
import { Button, Card, Form, Table, Tag, Typography } from 'antd'
import { useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { useHotspot, useLatestDaySectors } from '@/hooks/useHotspot'
import { useTelegraph } from '@/hooks/useTelegraph'
import { PAGE_SIZE, type SectorFundFlow } from '@ai-invest/shared'
import { useColorScheme } from '@/stores/settings'

import { FundSignalCard } from './components/FundSignalCard'
import { HotTimeline } from './components/HotTimeline'
import { HotspotFilters, type FilterForm } from './components/HotspotFilters'
import { SentimentCard } from './components/SentimentCard'
import { TopicCloud } from './components/TopicCloud'
import { columns, topTopicNames } from './utils'

import { DATE_FORMAT } from '@/utils/formatters'

function CategoryChip({
  label,
  active,
  onClick,
}: {
  label: string
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded px-2.5 py-1 text-xs transition-colors ${
        active
          ? 'bg-[#5e6ad2]/15 text-[#8b94e0]'
          : 'text-gray-500 hover:bg-gray-800 hover:text-gray-300'
      }`}
    >
      {label}
    </button>
  )
}

export function Hotspot() {
  useColorScheme()
  const queryClient = useQueryClient()
  const [form] = Form.useForm<FilterForm>()
  const [params, setParams] = useState({
    sectorType: '',
    tradeDate: '',
    page: 1,
    pageSize: PAGE_SIZE.table,
  })
  const [topic, setTopic] = useState<string | null>(null)

  const { data, isLoading } = useHotspot(params)
  const { data: sectors } = useLatestDaySectors()
  const { data: telegraph, isLoading: telegraphLoading } = useTelegraph(1, 15, undefined, true)

  const chipTopics = useMemo(() => topTopicNames(sectors ?? []), [sectors])
  const timelineItems = useMemo(() => {
    if (!topic) return telegraph?.items
    return (telegraph?.items ?? []).filter(
      (item) => (item.title ?? '').includes(topic) || (item.content ?? '').includes(topic),
    )
  }, [telegraph, topic])

  const handleSearch = (values: FilterForm) => {
    setParams({
      sectorType: values.sectorType || '',
      tradeDate: values.tradeDate ? values.tradeDate.format(DATE_FORMAT) : '',
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

      {/* 原型全宽卡：热点话题云（最新交易日涨幅 TOP 板块，热度分层） */}
      <Card
        title="热点话题云"
        variant="borderless"
        extra={<Tag color="green">实时更新</Tag>}
      >
        <TopicCloud />
      </Card>

      {/* 原型 grid-2-1 双栏：左实时热点时间线，右资金异动信号 + 市场情绪指数 */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <Card
          title="实时热点时间线"
          variant="borderless"
          className="xl:col-span-2"
          extra={(
            <div className="flex items-center gap-1">
              <CategoryChip label="全部" active={topic === null} onClick={() => setTopic(null)} />
              {chipTopics.map((name) => (
                <CategoryChip
                  key={name}
                  label={name}
                  active={topic === name}
                  onClick={() => setTopic(name)}
                />
              ))}
              <Link to="/telegraph" className="ml-1.5 text-xs text-gray-500 hover:text-[#8b94e0]">
                更多电报
              </Link>
            </div>
          )}
        >
          <HotTimeline items={timelineItems} loading={telegraphLoading} />
        </Card>
        <div className="flex flex-col gap-4">
          <Card title="资金异动信号" variant="borderless">
            <FundSignalCard />
          </Card>
          <Card title="市场情绪指数" variant="borderless">
            <SentimentCard />
          </Card>
        </div>
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
