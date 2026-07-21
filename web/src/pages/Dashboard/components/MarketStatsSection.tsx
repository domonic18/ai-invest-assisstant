import { Card, Skeleton, Tabs, Typography } from 'antd'

import type { IndexQuote, MarketStats } from '@ai-invest/shared'
import { SourceNote } from '@/components/common/SourceNote'
import { useColorScheme } from '@/stores/settings'
import { changeHex, fallColor, formatAmount, formatPercent, riseColor } from '@/utils/formatters'

import { IndexChartPanel } from './IndexChartPanel'

interface MarketStatsSectionProps {
  indices?: IndexQuote[]
  stats?: MarketStats
  loading: boolean
  tradeDate?: string
}

const EMOTION_STOPS = ['冰点', '偏冷', '温和', '偏热', '过热']

const INTRADAY_TABS = [
  { key: 'sh000001', label: '上证指数' },
  { key: 'sz399006', label: '创业板指' },
  { key: 'sh000688', label: '科创50' },
  { key: 'sh510300', label: '沪深300ETF', noIntraday: true },
  { key: 'CN00Y', label: '富时A50', noIntraday: true },
]

export function MarketStatsSection({ indices, stats, loading, tradeDate }: MarketStatsSectionProps) {
  useColorScheme()

  if (loading) {
    return <Skeleton active paragraph={{ rows: 8 }} />
  }

  const score = stats?.emotionScore

  return (
    <section className="space-y-4">
      <Typography.Text className="text-gray-400 text-xs tracking-widest">情绪面</Typography.Text>

      <Card variant="borderless" title="指数行情">
        {indices && indices.length > 0 ? (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
            {indices.map((item) => (
              <div key={item.code} className="rounded bg-[#1a1d24] p-3">
                <div className="text-xs text-gray-400">{item.name}</div>
                <div
                  className="text-lg font-semibold font-mono"
                  style={{ color: changeHex(item.changePct) }}
                >
                  {item.price.toLocaleString('zh-CN', { maximumFractionDigits: 2 })}
                </div>
                <div className="text-xs" style={{ color: changeHex(item.changePct) }}>
                  {formatPercent(item.changePct)}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-gray-500 text-sm py-4 text-center mb-4">
            该日无指数行情数据（非交易日）
          </div>
        )}
        <Tabs
          defaultActiveKey="sh000001"
          items={INTRADAY_TABS.map((tab) => ({
            key: tab.key,
            label: tab.label,
            children: (
              <IndexChartPanel
                code={tab.key}
                tradeDate={tradeDate}
                noIntraday={tab.noIntraday}
              />
            ),
          }))}
        />
        <SourceNote>新浪财经 · 指数实时行情与分钟级分时数据；多周期 K 线由本地指数日 K 聚合</SourceNote>
      </Card>

      <Card variant="borderless" title="成交量与涨跌统计">
        <div className="grid grid-cols-5 gap-2 mb-5 text-center">
          <div>
            <div className="text-xl font-semibold">{formatAmount(stats?.amount)}</div>
            <div className="text-xs text-gray-400">成交额</div>
            {stats?.amountChange != null && stats?.amountChangePct != null && (
              <div className="text-xs mt-0.5" style={{ color: changeHex(stats.amountChange) }}>
                较昨日 {stats.amountChange >= 0 ? '+' : '-'}{formatAmount(Math.abs(stats.amountChange))}
                {' '}({stats.amountChangePct >= 0 ? '+' : ''}{stats.amountChangePct.toFixed(1)}%)
              </div>
            )}
          </div>
          <div>
            <div className={`text-xl font-semibold ${riseColor()}`}>{stats?.upCount ?? '-'}</div>
            <div className="text-xs text-gray-400">上涨家数</div>
          </div>
          <div>
            <div className={`text-xl font-semibold ${riseColor()}`}>{stats?.limitUpCount ?? '-'}</div>
            <div className="text-xs text-gray-400">涨停家数</div>
          </div>
          <div>
            <div className={`text-xl font-semibold ${fallColor()}`}>{stats?.downCount ?? '-'}</div>
            <div className="text-xs text-gray-400">下跌家数</div>
          </div>
          <div>
            <div className={`text-xl font-semibold ${fallColor()}`}>{stats?.limitDownCount ?? '-'}</div>
            <div className="text-xs text-gray-400">跌停家数</div>
          </div>
        </div>

        <div className="text-sm font-medium mb-2">
          情绪温度
          <span className="text-xs text-gray-400 font-normal ml-2">
            综合涨停比、连板率、炸板率、涨跌比
          </span>
        </div>
        {score == null ? (
          <div className="text-gray-500 text-sm py-3 text-center rounded bg-[#1a1d24]">
            历史日期暂无情绪温度数据（缺少当日涨跌家数）
          </div>
        ) : (
          <>
            <div className="relative h-2 rounded bg-gradient-to-r from-[#2ea043] via-[#d29922] to-[#f85149]">
              <div
                className="absolute w-3 h-3 rounded-full bg-white border-2 border-gray-900 -top-0.5"
                style={{ left: `calc(${score}% - 6px)` }}
              />
            </div>
            <div className="flex justify-between text-xs text-gray-400 mt-1">
              {EMOTION_STOPS.map((label) => (
                <span
                  key={label}
                  className={label === stats?.emotionLabel ? 'text-amber-400 font-semibold' : ''}
                >
                  {label}
                </span>
              ))}
            </div>
            <div className="mt-3 rounded bg-amber-500/10 text-amber-400 text-xs p-2.5">
              情绪温度 <strong>{score.toFixed(0)}°</strong> · {stats?.emotionLabel ?? '-'} ·
              涨停比 {stats?.limitUpRatio ?? '-'}% ·
              连板率 {stats?.continuousRate != null ? `${(stats.continuousRate * 100).toFixed(1)}%` : '-'} ·
              炸板率 {stats?.brokenRate != null ? `${(stats.brokenRate * 100).toFixed(1)}%` : '-'}
            </div>
          </>
        )}
        <SourceNote>成交额为沪深交易所官方口径（不含北交所）· 上涨/下跌家数来自新浪财经全市场快照 · 涨跌停家数收盘后取自东方财富涨跌停池（不含 ST 股）</SourceNote>
      </Card>
    </section>
  )
}
