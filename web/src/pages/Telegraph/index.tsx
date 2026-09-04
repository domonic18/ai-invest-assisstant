import { ReloadOutlined } from '@ant-design/icons'
import {
  Button,
  Card,
  Empty,
  Pagination,
  Segmented,
  Space,
  Spin,
  Switch,
  Tag,
  Tooltip,
  Typography,
} from 'antd'
import dayjs from 'dayjs'
import { useState } from 'react'

import type { TelegraphItem } from '@ai-invest/shared'

import { useTelegraph } from '@/hooks/useTelegraph'
import { formatDateTime, formatRelativeTime } from '@/utils/formatters'

const IMPORTANCE_OPTIONS = [
  { label: '全部', value: 0 },
  { label: '仅重点', value: 2 },
]

const NEW_ITEM_WINDOW_SEC = 120
/** 最新电报滞后超过该秒数时提示采集可能断流。 */
const LAG_WARNING_SEC = 120

function importanceTag(importance: number | null) {
  if (importance === null) return null
  const presets: Record<number, { color: string; label: string }> = {
    3: { color: 'red', label: '重要' },
    2: { color: 'orange', label: '关注' },
    1: { color: 'blue', label: '一般' },
  }
  const preset = presets[importance] ?? { color: 'gold', label: `L${importance}` }
  return <Tag color={preset.color}>{preset.label}</Tag>
}

function isNew(item: TelegraphItem, now: number): boolean {
  return now - dayjs(item.publishTime).valueOf() < NEW_ITEM_WINDOW_SEC * 1000
}

function TelegraphEntry({ item, isNewItem }: { item: TelegraphItem; isNewItem: boolean }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2 flex-wrap">
        {importanceTag(item.importance)}
        {item.category && <Tag>{item.category}</Tag>}
        {item.title && <span className="text-sm font-semibold">{item.title}</span>}
        {isNewItem && <BadgeNew />}
      </div>
      {item.content && (
        <Typography.Paragraph className="!mb-0" ellipsis={{ rows: 3, expandable: true, symbol: '展开' }}>
          {item.content}
        </Typography.Paragraph>
      )}
      {(item.stockCodes.length > 0 || item.sourceUrl) && (
        <div className="flex items-center gap-2 flex-wrap">
          {item.stockCodes.map((code) => (
            <Tag key={code} className="font-mono">
              {code}
            </Tag>
          ))}
          <Typography.Link href={item.sourceUrl} target="_blank" rel="noreferrer" className="!text-xs">
            查看原文
          </Typography.Link>
        </div>
      )}
    </div>
  )
}

function BadgeNew() {
  return (
    <span className="inline-flex items-center gap-1 text-xs font-semibold text-red-500">
      <span className="inline-block size-1.5 rounded-full bg-red-500 animate-pulse" />
      NEW
    </span>
  )
}

export function Telegraph() {
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(30)
  const [minImportance, setMinImportance] = useState(0)
  const [autoRefresh, setAutoRefresh] = useState(true)

  const { data, isLoading, isFetching, refetch, dataUpdatedAt } = useTelegraph(
    page,
    pageSize,
    minImportance > 0 ? minImportance : undefined,
    autoRefresh,
  )

  const items = data?.items ?? []
  // publish_time 降序，首条即最新；滞后时长是采集链路是否健康的直观探针
  const latest = items[0]
  const latestLagSec = latest ? dayjs().diff(dayjs(latest.publishTime), 'second') : null
  const lagged = latestLagSec !== null && latestLagSec > LAG_WARNING_SEC
  const now = Date.now()

  return (
    <div className="space-y-4">
      <Typography.Title level={4} className="!mb-0">
        财联社电报
      </Typography.Title>

      <div className="flex items-center justify-between gap-3 flex-wrap">
        <Segmented
          options={IMPORTANCE_OPTIONS}
          value={minImportance}
          onChange={(v) => {
            setMinImportance(v as number)
            setPage(1)
          }}
        />
        <Space size="middle" className="items-center">
          {latest && (
            <Tooltip title={`最新电报发布于 ${formatDateTime(latest.publishTime)}`}>
              <Tag color={lagged ? 'warning' : 'success'} className="!m-0">
                最新 {formatRelativeTime(latest.publishTime)}
                {lagged && ' · 疑似断流'}
              </Tag>
            </Tooltip>
          )}
          <span className="text-xs opacity-60">
            {dataUpdatedAt ? `更新于 ${dayjs(dataUpdatedAt).format('HH:mm:ss')}` : ''}
            {isFetching ? ' · 拉取中' : ''}
          </span>
          <span className="flex items-center gap-1.5 text-sm">
            <Switch size="small" checked={autoRefresh} onChange={setAutoRefresh} />
            自动刷新
          </span>
          <Button size="small" icon={<ReloadOutlined />} onClick={() => refetch()} />
        </Space>
      </div>

      <Spin spinning={isLoading}>
        <Card variant="borderless">
          {items.length === 0 && !isLoading ? (
            <Empty description="暂无电报数据" />
          ) : (
            <div className="space-y-4">
              {items.map((item) => (
                <div key={item.clsMsgId} className="flex gap-3">
                  <span className="font-mono text-xs opacity-70 whitespace-nowrap pt-0.5">
                    {dayjs(item.publishTime).format('HH:mm:ss')}
                  </span>
                  <span className="flex-1 min-w-0 pb-4 border-b border-white/5">
                    <TelegraphEntry item={item} isNewItem={isNew(item, now)} />
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </Spin>

      <div className="flex justify-end">
        <Pagination
          current={page}
          pageSize={pageSize}
          total={data?.total ?? 0}
          showSizeChanger
          pageSizeOptions={[10, 30, 50, 100]}
          showTotal={(total) => `共 ${total} 条`}
          onChange={(next, nextSize) => {
            setPage(next)
            setPageSize(nextSize)
          }}
        />
      </div>
    </div>
  )
}
