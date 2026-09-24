/** 情绪流容器：筛选 chips + 跨日分组列表 + 分页；选中账号时切换为单账号时间线。 */

import { ArrowLeftOutlined } from '@ant-design/icons'
import { Button, Space, Tag, Tooltip } from 'antd'
import dayjs from 'dayjs'
import { useMemo, useState } from 'react'

import { PAGE_SIZE } from '@ai-invest/shared'
import type { ApiSocialAccountCard } from '@ai-invest/shared'

import { FeedList, FeedPagination, FeedToolbar } from '../FeedSkeleton'
import { groupByDay } from '../../logic'
import {
  useSentimentFeed,
  useSocialTimeline,
  type SentimentFilters,
} from '@/hooks/useSocialSentiment'

import { SentimentCard } from './SentimentCard'
import { StanceBadge } from './StanceBadge'
import { CATEGORY_LABELS } from './labels'
import type { ApiSocialStance, ApiSocialTimelineItem } from '@ai-invest/shared'

const STANCE_FILTERS: { label: string; value: ApiSocialStance | undefined }[] = [
  { label: '全部立场', value: undefined },
  { label: '看多', value: 'bullish' },
  { label: '看空', value: 'bearish' },
  { label: '中性', value: 'neutral' },
]

const HOUR_FILTERS: { label: string; value: number | undefined }[] = [
  { label: '不限时间', value: undefined },
  { label: '24h', value: 24 },
  { label: '3天', value: 72 },
  { label: '7天', value: 168 },
]

const CATEGORY_FILTERS: { label: string; value: string | undefined }[] = [
  { label: '全部分类', value: undefined },
  { label: CATEGORY_LABELS.macro_policy, value: 'macro_policy' },
  { label: CATEGORY_LABELS.finance_kol, value: 'finance_kol' },
  { label: CATEGORY_LABELS.industry, value: 'industry' },
]

interface SentimentStreamProps {
  /** 时间范围（小时）由 SentimentView 持有，与账号卡统计窗口联动 */
  hours: number | undefined
  onHoursChange: (hours: number | undefined) => void
  /** 选中的账号（非空时渲染单账号时间线） */
  account: ApiSocialAccountCard | null
  onClearAccount: () => void
}

export function SentimentStream({
  hours,
  onHoursChange,
  account,
  onClearAccount,
}: SentimentStreamProps) {
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(PAGE_SIZE.feed)
  const [filters, setFilters] = useState<SentimentFilters>({})
  const [autoRefresh, setAutoRefresh] = useState(true)

  const feed = useSentimentFeed(page, pageSize, { ...filters, hours }, autoRefresh)

  return (
    <div className="space-y-3">
      {account ? (
        <TimelinePanel
          account={account}
          page={page}
          pageSize={pageSize}
          onPage={setPage}
          onPageSize={setPageSize}
          onBack={() => {
            onClearAccount()
            setPage(1)
          }}
        />
      ) : (
        <FeedPanel
          feed={feed}
          filters={filters}
          hours={hours}
          onHoursChange={(next) => {
            onHoursChange(next)
            setPage(1)
          }}
          onFiltersChange={(next) => {
            setFilters(next)
            setPage(1)
          }}
          autoRefresh={autoRefresh}
          onAutoRefreshChange={setAutoRefresh}
          page={page}
          pageSize={pageSize}
          total={feed.data?.total ?? 0}
          onPage={setPage}
          onPageSize={setPageSize}
        />
      )}
    </div>
  )
}

interface FeedPanelProps {
  feed: ReturnType<typeof useSentimentFeed>
  filters: SentimentFilters
  hours: number | undefined
  onHoursChange: (hours: number | undefined) => void
  onFiltersChange: (next: SentimentFilters) => void
  autoRefresh: boolean
  onAutoRefreshChange: (checked: boolean) => void
  page: number
  pageSize: number
  total: number
  onPage: (page: number) => void
  onPageSize: (size: number) => void
}

function FeedPanel({
  feed,
  filters,
  hours,
  onHoursChange,
  onFiltersChange,
  autoRefresh,
  onAutoRefreshChange,
  page,
  pageSize,
  total,
  onPage,
  onPageSize,
}: FeedPanelProps) {
  const items = useMemo(() => feed.data?.items ?? [], [feed.data])
  const groups = useMemo(
    () => groupByDay(items.map((item) => ({ ...item, publishTime: item.publishedAt }))),
    [items],
  )

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-4 flex-wrap">
          <Space size={[6, 6]} wrap>
            {CATEGORY_FILTERS.map((filter) => (
              <Tag.CheckableTag
                key={filter.label}
                checked={filters.category === filter.value}
                onChange={() => onFiltersChange({ ...filters, category: filter.value })}
              >
                {filter.label}
              </Tag.CheckableTag>
            ))}
          </Space>
          <Space size={[6, 6]} wrap>
            {STANCE_FILTERS.map((filter) => (
              <Tag.CheckableTag
                key={filter.label}
                checked={filters.stance === filter.value}
                onChange={() => onFiltersChange({ ...filters, stance: filter.value })}
              >
                {filter.label}
              </Tag.CheckableTag>
            ))}
          </Space>
          <Space size={[6, 6]} wrap>
            {HOUR_FILTERS.map((filter) => (
              <Tag.CheckableTag
                key={filter.label}
                checked={hours === filter.value}
                onChange={() => onHoursChange(filter.value)}
              >
                {filter.label}
              </Tag.CheckableTag>
            ))}
            <Tooltip title="仅显示置信度 ≥ 80% 的强信号">
              <Tag.CheckableTag
                checked={filters.strongOnly ?? false}
                onChange={(checked) => onFiltersChange({ ...filters, strongOnly: checked })}
              >
                仅强信号
              </Tag.CheckableTag>
            </Tooltip>
          </Space>
        </div>
        <FeedToolbar
          dataUpdatedAt={feed.dataUpdatedAt}
          isFetching={feed.isFetching}
          autoRefresh={autoRefresh}
          onAutoRefreshChange={onAutoRefreshChange}
          onRefresh={() => feed.refetch()}
        />
      </div>

      <FeedList
        groups={groups}
        isLoading={feed.isLoading}
        emptyText="暂无情绪数据（等待采集与 AI 判断完成）"
        getKey={(item) => item.postId}
      >
        {(item) => <SentimentCard item={item} />}
      </FeedList>

      <FeedPagination
        page={page}
        pageSize={pageSize}
        total={total}
        onChange={(next, nextSize) => {
          onPage(next)
          onPageSize(nextSize)
        }}
      />
    </div>
  )
}

interface TimelinePanelProps {
  account: ApiSocialAccountCard
  page: number
  pageSize: number
  onPage: (page: number) => void
  onPageSize: (size: number) => void
  onBack: () => void
}

/** 单账号时间线：立场轨迹按列表顺序派生（新 → 旧）， badges 即轨迹。 */
function TimelinePanel({
  account,
  page,
  pageSize,
  onPage,
  onPageSize,
  onBack,
}: TimelinePanelProps) {
  const { data, isLoading, isFetching, refetch, dataUpdatedAt } = useSocialTimeline(
    account.id,
    page,
    pageSize,
  )
  const items = useMemo(() => data?.items ?? [], [data])
  const groups = useMemo(
    () => groupByDay(items.map((item) => ({ ...item, publishTime: item.publishedAt }))),
    [items],
  )

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <Space>
          <Button size="small" icon={<ArrowLeftOutlined />} onClick={onBack}>
            返回情绪流
          </Button>
          <span className="text-sm font-medium">{account.alias} 的时间线</span>
          {account.latestStance && (
            <StanceBadge
              stance={account.latestStance}
              confidence={account.latestConfidence}
            />
          )}
        </Space>
        <FeedToolbar
          dataUpdatedAt={dataUpdatedAt}
          isFetching={isFetching}
          autoRefresh={false}
          onAutoRefreshChange={() => undefined}
          onRefresh={() => refetch()}
        />
      </div>

      <FeedList
        groups={groups}
        isLoading={isLoading}
        emptyText="该账号暂无已判断内容"
        getKey={(item) => item.postId}
      >
        {(item) => <TimelineRow item={item} />}
      </FeedList>

      <FeedPagination
        page={page}
        pageSize={pageSize}
        total={data?.total ?? 0}
        onChange={(next, nextSize) => {
          onPage(next)
          onPageSize(nextSize)
        }}
      />
    </div>
  )
}

function TimelineRow({ item }: { item: ApiSocialTimelineItem }) {
  return (
    <div className="flex gap-3 py-3 border-b border-white/5">
      <span className="font-mono text-xs opacity-70 whitespace-nowrap pt-0.5">
        {dayjs(item.publishedAt).format('MM-DD HH:mm')}
      </span>
      <div className="flex-1 min-w-0 space-y-1">
        <div className="flex items-center gap-2">
          <StanceBadge stance={item.stance} confidence={item.confidence} />
          {item.transcriptMissing && <span className="text-xs opacity-40">未转写</span>}
        </div>
        {item.title && <div className="text-sm font-medium line-clamp-1">{item.title}</div>}
        <div className="text-xs opacity-70">{item.summary}</div>
      </div>
    </div>
  )
}
