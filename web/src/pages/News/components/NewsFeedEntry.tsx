/**
 * 新闻流条目渲染：电报条目（AI 分级/订阅/标的/跟踪线）与快讯条目（基础流）。
 * 分级色条常量与「新讯息」判定在 logic.ts。
 */

import { AimOutlined, LinkOutlined, StarFilled } from '@ant-design/icons'
import { Button, Tag, Tooltip, Typography, message } from 'antd'

import type { TelegraphItem } from '@ai-invest/shared'

import type { NewsFlashItem } from '@/api/mappers/news'
import { StockLinkTag } from '@/components/common/StockLinkTag'
import { useCreateNewsStory } from '@/hooks/useNewsFocus'
import { isNoiseCategory, isNoiseImportance } from '../logic'

function importanceTag(importance: number | null) {
  if (importance === null || isNoiseImportance(importance)) return null
  const presets: Record<number, { color: string; label: string }> = {
    3: { color: 'red', label: '重要' },
    2: { color: 'orange', label: '关注' },
  }
  const preset = presets[importance] ?? { color: 'gold', label: `L${importance}` }
  return <Tag color={preset.color}>{preset.label}</Tag>
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

export function NewsEntry({ item, isNewItem }: { item: TelegraphItem; isNewItem: boolean }) {
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

/** 快讯条目（基础流：title + summary + 时间 + 原文链接，无 AI 分级/订阅/标的）。 */
export function FlashEntry({ item }: { item: NewsFlashItem }) {
  const summary = item.summary ?? item.content
  return (
    <div className="space-y-1">
      {item.title && <span className="text-sm font-semibold">{item.title}</span>}
      {summary && (
        <Typography.Paragraph
          className="!mb-0"
          ellipsis={{ rows: 3, expandable: true, symbol: '展开' }}
        >
          {summary}
        </Typography.Paragraph>
      )}
      {item.sourceUrl && (
        <Tooltip title="查看原文（东财）">
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
    </div>
  )
}
