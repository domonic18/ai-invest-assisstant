/**
 * 新闻页实时电报容器：渠道 chips 行 + 电报流（AI 分级/订阅筛选）与东财快讯基础流切换。
 * 条目渲染见 NewsFeedEntry.tsx，分组列表/工具条/分页骨架见 FeedSkeleton.tsx。
 */

import { VerticalAlignTopOutlined } from '@ant-design/icons'
import { Space, Tag, Tooltip, theme } from 'antd'
import dayjs from 'dayjs'
import { useEffect, useMemo, useState } from 'react'

import { PAGE_SIZE, type ApiNewsChannel } from '@ai-invest/shared'

import { formatDateTime, formatRelativeTime } from '@/utils/formatters'
import { useNewsFlash } from '@/hooks/useNewsFlash'
import { useTelegraph } from '@/hooks/useTelegraph'
import { FlashEntry, NewsEntry } from './NewsFeedEntry'
import { FeedList, FeedPagination, FeedToolbar } from './FeedSkeleton'
import {
  BAND_BAR_CLASS,
  countNewMessages,
  groupByDay,
  isChannelWired,
  isNew,
  scoreBand,
  SCORE_HIGH_MIN,
  SCORE_MID_MIN,
} from '../logic'

/** 分级筛选：全部=不过滤（含未分级）；低=仅已分级（min_ai_score=0 排除未分级）。 */
const SCORE_FILTERS: { label: string; value: number | undefined }[] = [
  { label: '全部', value: undefined },
  { label: `高 ≥${SCORE_HIGH_MIN}`, value: SCORE_HIGH_MIN },
  { label: `中 ≥${SCORE_MID_MIN}`, value: SCORE_MID_MIN },
  { label: '已分级', value: 0 },
]

/** 最新电报滞后超过该秒数时提示采集可能断流。 */
const LAG_WARNING_SEC = 120

/** 财联社电报流：AI 分级三档色条 + 分级/订阅筛选 + 新讯息浮条 + 跨日分隔。 */
function TelegraphFeed() {
  const { token } = theme.useToken()
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(PAGE_SIZE.feed)
  const [minAiScore, setMinAiScore] = useState<number | undefined>(undefined)
  const [subscriptionOnly, setSubscriptionOnly] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [seenTopId, setSeenTopId] = useState<number | null>(null)

  const { data, isLoading, isFetching, refetch, dataUpdatedAt } = useTelegraph(
    page,
    pageSize,
    undefined,
    minAiScore,
    autoRefresh,
    subscriptionOnly,
  )

  const items = useMemo(() => data?.items ?? [], [data])
  // 首次加载记录页首 id 作为「已见」基准；翻页不重置（第 2 页 id 均更旧，计数自然为 0）
  useEffect(() => {
    if (seenTopId === null && items.length > 0) {
      setSeenTopId(items[0].clsMsgId)
    }
  }, [items, seenTopId])
  const newCount = countNewMessages(items, seenTopId)

  // publish_time 降序，首条即最新；滞后时长是采集链路是否健康的直观探针
  const latest = items[0]
  const latestLagSec = latest
    ? dayjs().diff(dayjs(latest.publishTime), 'second')
    : null
  const lagged = latestLagSec !== null && latestLagSec > LAG_WARNING_SEC
  const now = Date.now()
  const groups = useMemo(() => groupByDay(items), [items])

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-4 flex-wrap">
          <Space size={[6, 6]} wrap>
            {SCORE_FILTERS.map((filter) => (
              <Tag.CheckableTag
                key={filter.label}
                checked={minAiScore === filter.value}
                onChange={() => {
                  setMinAiScore(filter.value)
                  setPage(1)
                }}
              >
                {filter.label}
              </Tag.CheckableTag>
            ))}
          </Space>
          <Tooltip title="仅显示命中我订阅关键词的电报（页头「我的订阅」管理关键词）">
            <Tag.CheckableTag
              checked={subscriptionOnly}
              onChange={(checked) => {
                setSubscriptionOnly(checked)
                setPage(1)
              }}
            >
              ★ 仅看订阅命中
            </Tag.CheckableTag>
          </Tooltip>
        </div>
        <FeedToolbar
          dataUpdatedAt={dataUpdatedAt}
          isFetching={isFetching}
          autoRefresh={autoRefresh}
          onAutoRefreshChange={setAutoRefresh}
          onRefresh={() => refetch()}
          leading={
            latest ? (
              <Tooltip title={`最新电报发布于 ${formatDateTime(latest.publishTime)}`}>
                <Tag color={lagged ? 'warning' : 'success'} className="!m-0">
                  最新 {formatRelativeTime(latest.publishTime)}
                  {lagged && ' · 疑似断流'}
                </Tag>
              </Tooltip>
            ) : undefined
          }
        />
      </div>

      {newCount > 0 && (
        <button
          type="button"
          onClick={() => {
            if (items.length > 0) setSeenTopId(items[0].clsMsgId)
            window.scrollTo({ top: 0, behavior: 'smooth' })
          }}
          className="flex items-center justify-center gap-2 w-full py-2 text-xs border border-dashed rounded-lg cursor-pointer"
          style={{
            color: token.colorPrimary,
            background: token.colorPrimaryBg,
            borderColor: token.colorPrimaryBorder,
          }}
        >
          <VerticalAlignTopOutlined />
          <b>{newCount} 条新讯息</b>
          <span className="opacity-50">点击回到顶部载入，不打断当前浏览位置</span>
        </button>
      )}

      <FeedList
        groups={groups}
        isLoading={isLoading}
        emptyText="暂无电报数据"
        getKey={(item) => item.clsMsgId}
      >
        {(item) => (
          <div className="flex gap-3 py-3 border-b border-white/5">
            <Tooltip
              title={
                item.aiScore === null ? 'AI 分级待完成' : `AI 重要度 ${item.aiScore}`
              }
            >
              <span
                className={`w-[3px] rounded shrink-0 self-stretch ${BAND_BAR_CLASS[scoreBand(item.aiScore)]}`}
              />
            </Tooltip>
            <span className="font-mono text-xs opacity-70 whitespace-nowrap pt-0.5">
              {dayjs(item.publishTime).format('HH:mm:ss')}
            </span>
            <span className="flex-1 min-w-0">
              <NewsEntry item={item} isNewItem={isNew(item, now)} />
            </span>
          </div>
        )}
      </FeedList>

      <FeedPagination
        page={page}
        pageSize={pageSize}
        total={data?.total ?? 0}
        onChange={(next, nextSize) => {
          setPage(next)
          setPageSize(nextSize)
        }}
      />
    </div>
  )
}

/** 东财快讯流：基础流跨日分组 + 分页 + 自动刷新（无 AI 分级/订阅/标的）。 */
function FlashFeedView() {
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(PAGE_SIZE.feed)
  const [autoRefresh, setAutoRefresh] = useState(true)

  const { data, isLoading, isFetching, refetch, dataUpdatedAt } = useNewsFlash(
    page,
    pageSize,
    autoRefresh,
  )

  const items = useMemo(() => data?.items ?? [], [data])
  const groups = useMemo(() => groupByDay(items), [items])

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-end gap-3 flex-wrap">
        <FeedToolbar
          dataUpdatedAt={dataUpdatedAt}
          isFetching={isFetching}
          autoRefresh={autoRefresh}
          onAutoRefreshChange={setAutoRefresh}
          onRefresh={() => refetch()}
        />
      </div>

      <FeedList
        groups={groups}
        isLoading={isLoading}
        emptyText="暂无快讯数据"
        getKey={(item) => item.id}
      >
        {(item) => (
          <div className="flex gap-3 py-3 border-b border-white/5">
            <span className="font-mono text-xs opacity-70 whitespace-nowrap pt-0.5">
              {dayjs(item.publishTime).format('HH:mm:ss')}
            </span>
            <span className="flex-1 min-w-0">
              <FlashEntry item={item} />
            </span>
          </div>
        )}
      </FeedList>

      <FeedPagination
        page={page}
        pageSize={pageSize}
        total={data?.total ?? 0}
        onChange={(next, nextSize) => {
          setPage(next)
          setPageSize(nextSize)
        }}
      />
    </div>
  )
}

interface NewsFeedViewProps {
  /** 渠道 chips 数据源（从 /news/channels 渲染，不写死渠道清单）。 */
  channels: ApiNewsChannel[]
}

/** 实时电报容器：共享渠道 chips 行，按选中渠道切换数据源。 */
export function NewsFeedView({ channels }: NewsFeedViewProps) {
  const [channelKey, setChannelKey] = useState<string>('all')

  return (
    <div className="space-y-3">
      <Space size={[6, 6]} wrap>
        {/* 渠道 chips 只渲染已接入数据源的渠道；未接入渠道仅在监控条展示健康，不出 chip */}
        <Tag.CheckableTag
          checked={channelKey === 'all'}
          onChange={() => setChannelKey('all')}
        >
          全部渠道
        </Tag.CheckableTag>
        {channels
          .filter((channel) => isChannelWired(channel.key))
          .map((channel) => (
            <Tag.CheckableTag
              key={channel.key}
              checked={channelKey === channel.key}
              onChange={() => setChannelKey(channel.key)}
            >
              {channel.name}
            </Tag.CheckableTag>
          ))}
      </Space>

      {channelKey === 'eastmoney_flash_news' ? <FlashFeedView /> : <TelegraphFeed />}
    </div>
  )
}
