import {
  AimOutlined,
  LinkOutlined,
  ReloadOutlined,
  StarFilled,
  VerticalAlignTopOutlined,
} from '@ant-design/icons'
import {
  Button,
  Card,
  Empty,
  Pagination,
  Space,
  Spin,
  Switch,
  Tag,
  theme,
  Tooltip,
  Typography,
  message,
} from 'antd'
import dayjs from 'dayjs'
import { Fragment, useEffect, useMemo, useState } from 'react'

import { PAGE_SIZE, type ApiNewsChannel, type TelegraphItem } from '@ai-invest/shared'

import { StockLinkTag } from '@/components/common/StockLinkTag'
import { useCreateNewsStory } from '@/hooks/useNewsFocus'
import { useTelegraph } from '@/hooks/useTelegraph'
import { formatDateTime, formatRelativeTime } from '@/utils/formatters'
import {
  countNewMessages,
  groupByDay,
  isChannelWired,
  isNoiseCategory,
  isNoiseImportance,
  scoreBand,
  SCORE_HIGH_MIN,
  SCORE_MID_MIN,
  type ScoreBand,
} from '../logic'

/** AI 分级三档色条（null=未分级灰条；阈值见 logic.ts）。 */
const BAND_BAR_CLASS: Record<ScoreBand, string> = {
  high: 'bg-red-500',
  mid: 'bg-amber-500',
  low: 'bg-white/20',
  unscored: 'bg-white/10',
}

/** 分级筛选：全部=不过滤（含未分级）；低=仅已分级（min_ai_score=0 排除未分级）。 */
const SCORE_FILTERS: { label: string; value: number | undefined }[] = [
  { label: '全部', value: undefined },
  { label: `高 ≥${SCORE_HIGH_MIN}`, value: SCORE_HIGH_MIN },
  { label: `中 ≥${SCORE_MID_MIN}`, value: SCORE_MID_MIN },
  { label: '已分级', value: 0 },
]

const NEW_ITEM_WINDOW_SEC = 120
/** 最新电报滞后超过该秒数时提示采集可能断流。 */
const LAG_WARNING_SEC = 120

function importanceTag(importance: number | null) {
  if (importance === null || isNoiseImportance(importance)) return null
  const presets: Record<number, { color: string; label: string }> = {
    3: { color: 'red', label: '重要' },
    2: { color: 'orange', label: '关注' },
  }
  const preset = presets[importance] ?? { color: 'gold', label: `L${importance}` }
  return <Tag color={preset.color}>{preset.label}</Tag>
}

function isNew(item: TelegraphItem, now: number): boolean {
  return now - dayjs(item.publishTime).valueOf() < NEW_ITEM_WINDOW_SEC * 1000
}

function BadgeNew() {
  return (
    <span className="inline-flex items-center gap-1 text-xs font-semibold text-red-500">
      <span className="inline-block size-1.5 rounded-full bg-red-500 animate-pulse" />
      NEW
    </span>
  )
}

/** 关联标的 Tag：名称 + 当日涨跌幅（scheme 着色），点击直达个股页。 */
function StockTags({ item }: { item: TelegraphItem }) {
  if (item.stocks.length > 0) {
    return (
      <>
        {item.stocks.map((stock) => (
          <StockLinkTag
            key={stock.code}
            code={stock.code}
            name={stock.name}
            changePct={stock.changePct ?? null}
          />
        ))}
      </>
    )
  }
  return (
    <>
      {item.stockCodes.map((code) => (
        <Tag key={code} className="font-mono">
          {code}
        </Tag>
      ))}
    </>
  )
}

function NewsEntry({ item, isNewItem }: { item: TelegraphItem; isNewItem: boolean }) {
  const createStory = useCreateNewsStory()
  const [messageApi, contextHolder] = message.useMessage()

  return (
    <div className="space-y-1">
      {contextHolder}
      <div className="flex items-center gap-2 flex-wrap">
        {importanceTag(item.importance)}
        {!isNoiseCategory(item.category) && item.category && <Tag>{item.category}</Tag>}
        {item.title && <span className="text-sm font-semibold">{item.title}</span>}
        {item.subscribed && (
          <Tooltip title="命中我的订阅关键词">
            <StarFilled className="text-xs text-amber-400" />
          </Tooltip>
        )}
        {isNewItem && <BadgeNew />}
      </div>
      {item.content && (
        <Typography.Paragraph
          className="!mb-0"
          ellipsis={{ rows: 3, expandable: true, symbol: '展开' }}
        >
          {item.content}
        </Typography.Paragraph>
      )}
      <div className="flex items-center gap-2 flex-wrap">
        <StockTags item={item} />
        {item.sourceUrl && (
          <Tooltip title="查看原文（cls.cn）">
            <Typography.Link
              href={item.sourceUrl}
              target="_blank"
              rel="noreferrer"
              aria-label="查看原文"
            >
              <LinkOutlined />
            </Typography.Link>
          </Tooltip>
        )}
        <Tooltip title="跟踪此事件（手动建线）">
          <Button
            type="text"
            size="small"
            icon={<AimOutlined />}
            aria-label="跟踪此事件"
            loading={
              createStory.isPending &&
              createStory.variables?.itemId === String(item.clsMsgId)
            }
            onClick={() =>
              createStory.mutate(
                { source: 'cls_telegraph', itemId: String(item.clsMsgId) },
                {
                  onSuccess: () =>
                    messageApi.success('已创建跟踪线，见「重点与跟踪」视图'),
                  onError: (error) =>
                    messageApi.error(error.message || '创建跟踪线失败'),
                },
              )
            }
          />
        </Tooltip>
      </div>
    </div>
  )
}

interface NewsFeedViewProps {
  /** 渠道 chips 数据源（从 /news/channels 渲染，不写死渠道清单）。 */
  channels: ApiNewsChannel[]
}

/** 实时电报视图：AI 分级三档色条 + 分级/渠道筛选 + 新讯息浮条 + 跨日分隔。 */
export function NewsFeedView({ channels }: NewsFeedViewProps) {
  const { token } = theme.useToken()
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(PAGE_SIZE.feed)
  const [minAiScore, setMinAiScore] = useState<number | undefined>(undefined)
  const [channelKey, setChannelKey] = useState<string>('all')
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
          <Space size={[6, 6]} wrap>
            {/* 渠道 chips 从注册表渲染；已接入数据源的可选中筛选（当前单源，等价全量） */}
            <Tag.CheckableTag
              checked={channelKey === 'all'}
              onChange={() => setChannelKey('all')}
            >
              全部渠道
            </Tag.CheckableTag>
            {channels.map((channel) =>
              isChannelWired(channel.key) ? (
                <Tag.CheckableTag
                  key={channel.key}
                  checked={channelKey === channel.key}
                  onChange={() => setChannelKey(channel.key)}
                >
                  {channel.name}
                </Tag.CheckableTag>
              ) : (
                <Tooltip key={channel.key} title="该渠道数据接入中（迭代 4）">
                  <Tag.CheckableTag
                    checked={false}
                    className="!cursor-not-allowed !opacity-40"
                  >
                    {channel.name}
                  </Tag.CheckableTag>
                </Tooltip>
              ),
            )}
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

      <Spin spinning={isLoading}>
        <Card variant="borderless">
          {items.length === 0 && !isLoading ? (
            <Empty description="暂无电报数据" />
          ) : (
            <div>
              {groups.map((group, groupIndex) => (
                <Fragment key={group.day}>
                  {groupIndex > 0 && (
                    <div className="flex items-center gap-2.5 my-3 text-xs opacity-40">
                      <span className="flex-1 h-px bg-white/10" />
                      以下为 {group.label} 资讯
                      <span className="flex-1 h-px bg-white/10" />
                    </div>
                  )}
                  {group.items.map((item) => (
                    <div key={item.clsMsgId} className="flex gap-3 py-3 border-b border-white/5">
                      <Tooltip
                        title={
                          item.aiScore === null
                            ? 'AI 分级待完成'
                            : `AI 重要度 ${item.aiScore}`
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
                  ))}
                </Fragment>
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
