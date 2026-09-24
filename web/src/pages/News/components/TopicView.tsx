import {
  DownOutlined,
  FireOutlined,
  QuestionCircleOutlined,
  UpOutlined,
} from '@ant-design/icons'
import { Button, Card, Empty, Segmented, Spin, Tag, Tooltip } from 'antd'
import { useState } from 'react'

import type { ApiNewsTopic, ApiTopicVotes } from '@ai-invest/shared'

import { StockLinkTag } from '@/components/common/StockLinkTag'
import { useNewsTopics } from '@/hooks/useNewsTopics'

type TopicSession = 'intraday' | 'post'

const SESSION_LABELS: Record<TopicSession, string> = {
  intraday: '盘中 11:35',
  post: '盘后 16:35',
}

const SENTIMENT_COLOR: Record<ApiNewsTopic['sentiment'], string> = {
  利好: 'red',
  利空: 'green',
  分歧: 'gold',
}

/** 情绪票数三段分布条（利好红 / 中性灰 / 利空绿，国内配色习惯）；hover 出 ? 说明口径。 */
function VotesBar({ votes }: { votes: ApiTopicVotes }) {
  const total = votes.bullish + votes.bearish + votes.neutral
  const parts = [
    { key: 'bullish', value: votes.bullish, cls: 'bg-red-500' },
    { key: 'neutral', value: votes.neutral, cls: 'bg-gray-400' },
    { key: 'bearish', value: votes.bearish, cls: 'bg-green-500' },
  ]
  return (
    <Tooltip
      title={
        <div className="space-y-1">
          <div>利好 {votes.bullish} · 中性 {votes.neutral} · 利空 {votes.bearish}</div>
          <div className="opacity-70">
            情绪票数：AI 聚类时对该主题下每条资讯判定利多 / 利空 / 中性的统计分布
          </div>
        </div>
      }
    >
      <div className="group inline-flex items-center gap-1.5 cursor-default">
        <div className="flex h-1.5 w-32 rounded-full overflow-hidden bg-white/10">
          {parts.map(
            (part) =>
              part.value > 0 && (
                <div
                  key={part.key}
                  className={part.cls}
                  style={{ width: `${(part.value / Math.max(total, 1)) * 100}%` }}
                />
              ),
          )}
        </div>
        <span className="text-xs opacity-60">{total} 票</span>
        <QuestionCircleOutlined className="text-[10px] opacity-0 group-hover:opacity-60 transition-opacity" />
      </div>
    </Tooltip>
  )
}

/** 热度构成透明化展开：资讯量 / 板块涨幅 / 主力资金净流入 + T-1 标注。 */
function HeatFactors({ topic }: { topic: ApiNewsTopic }) {
  const f = topic.factors
  const isStale = f.asOfTradeDate !== null && f.sectorChangePct !== null
  return (
    <div className="space-y-1 text-xs">
      <div className="flex justify-between">
        <span className="opacity-60">资讯量</span>
        <span className="font-mono">{f.newsCount} 条</span>
      </div>
      <div className="flex justify-between">
        <span className="opacity-60">板块涨幅</span>
        <span className="font-mono">
          {f.sectorChangePct === null ? '—' : `${f.sectorChangePct.toFixed(2)}%`}
        </span>
      </div>
      <div className="flex justify-between">
        <span className="opacity-60">主力净流入</span>
        <span className="font-mono">
          {f.fundFlowNet === null ? '—' : `${(f.fundFlowNet / 1e8).toFixed(2)} 亿`}
        </span>
      </div>
      {isStale && (
        <Tooltip title="板块行情为收盘快照，盘中榜使用最近收盘数据">
          <Tag className="!m-0 !text-[10px] !leading-4" color="orange">
            板块口径 {f.asOfTradeDate}（T-1 收盘）
          </Tag>
        </Tooltip>
      )}
    </div>
  )
}

/** 主题卡：排名 + 情绪 + 热度 + 传导链展开。 */
function TopicCard({ topic, rank }: { topic: ApiNewsTopic; rank: number }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <Card size="small" className="!bg-white/[0.03]">
      <div className="space-y-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span
            className={`w-6 h-6 inline-flex items-center justify-center rounded text-xs font-bold font-mono shrink-0 ${
              rank <= 3 ? 'bg-red-500/20 text-red-400' : 'bg-white/10 opacity-70'
            }`}
          >
            {rank}
          </span>
          <span className="text-sm font-semibold">{topic.title}</span>
          <Tag color={SENTIMENT_COLOR[topic.sentiment]} className="!m-0">
            {topic.sentiment}
          </Tag>
          <VotesBar votes={topic.votes} />
          <span className="flex items-center gap-1 text-xs text-orange-400 ml-auto">
            <FireOutlined />
            <b className="font-mono">{topic.heat.toFixed(0)}</b>
          </span>
        </div>

        <div className="flex items-center gap-3 flex-wrap text-xs">
          <span className="opacity-60">{topic.newsCount} 条资讯</span>
          {topic.sectors.map((sector) => (
            <Tag key={sector.name} className="!m-0 !text-xs">
              {sector.name}
              {sector.changePct !== null && (
                <span className={sector.changePct >= 0 ? 'text-red-400' : 'text-green-400'}>
                  {' '}
                  {sector.changePct >= 0 ? '+' : ''}
                  {sector.changePct.toFixed(2)}%
                </span>
              )}
            </Tag>
          ))}
        </div>

        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="text-xs opacity-60 mb-1">热度构成（资讯量×板块涨幅×主力净流入）</div>
            <HeatFactors topic={topic} />
          </div>
          <Button
            type="link"
            size="small"
            className="!px-0 shrink-0"
            onClick={() => setExpanded((v) => !v)}
          >
            传导链（{topic.chain.length} 步）
            {expanded ? <UpOutlined /> : <DownOutlined />}
          </Button>
        </div>

        {expanded && (
          <div className="space-y-1.5 pt-1 border-t border-white/5">
            {topic.chain.map((step, index) => (
              <div key={index} className="text-xs">
                <span className="opacity-50">{index === 0 ? '起点' : step.link}：</span>
                {step.event}
                {step.stocks.length > 0 && (
                  <span className="ml-2 inline-flex gap-1 flex-wrap align-middle">
                    {step.stocks.map((stock) => (
                      <StockLinkTag
                        key={stock.code ?? stock.name}
                        code={stock.code}
                        name={stock.name}
                        changePct={stock.changePct}
                      />
                    ))}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  )
}

/** 词云：按词频缩放字号（纯 CSS 渲染，不引入图表库）。 */
function Wordcloud({ words }: { words: { word: string; count: number }[] }) {
  if (words.length === 0) return null
  const max = words[0].count
  const min = words[words.length - 1].count
  return (
    <div className="flex flex-wrap gap-x-3 gap-y-1 items-baseline">
      {words.map((item) => {
        const ratio = max > min ? (item.count - min) / (max - min) : 0.5
        const size = 12 + ratio * 14
        return (
          <span
            key={item.word}
            style={{ fontSize: size }}
            className={
              ratio > 0.66 ? 'text-red-400 font-semibold' : 'text-white/80'
            }
          >
            {item.word}
          </span>
        )
      })}
    </div>
  )
}

/** 热点主题视图：session 切换 + 词云 + 主题卡榜（热度/情绪/传导链）。 */
export function TopicView() {
  const [sessionKey, setSessionKey] = useState<TopicSession>('post')
  const { data, isLoading } = useNewsTopics(sessionKey)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <Segmented<TopicSession>
          value={sessionKey}
          onChange={setSessionKey}
          options={(
            Object.keys(SESSION_LABELS) as TopicSession[]
          ).map((key) => ({ label: SESSION_LABELS[key], value: key }))}
        />
        {data?.generatedAt && (
          <span className="text-xs opacity-50">
            生成于 {data.generatedAt.replace('T', ' ').slice(5, 16)} · 数据日期{' '}
            {data.tradeDate}
          </span>
        )}
      </div>

      <Spin spinning={isLoading}>
        {(data?.topics.length ?? 0) === 0 && !isLoading ? (
          <Card variant="borderless">
            <Empty description="该时段暂无主题快照（盘中 11:35 / 盘后 16:35 定时生成）" />
          </Card>
        ) : (
          <div className="space-y-4">
            {(data?.wordcloud.length ?? 0) > 0 && (
              <Card size="small" title="今日热词" variant="borderless">
                <Wordcloud words={data?.wordcloud ?? []} />
              </Card>
            )}
            <div className="space-y-3">
              {(data?.topics ?? []).map((topic, index) => (
                <TopicCard key={topic.title} topic={topic} rank={index + 1} />
              ))}
            </div>
          </div>
        )}
      </Spin>
    </div>
  )
}
