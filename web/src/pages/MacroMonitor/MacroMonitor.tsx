import { Card, Empty, Typography } from 'antd'
import { Link } from 'react-router-dom'
import { useMemo, useState } from 'react'

import type { GlobalIndexQuote, IndexQuote } from '@ai-invest/shared'

import { GhostCard, MacroCard } from './MacroCard'
import { FedWatchSection } from './FedWatchSection'
import { HistoryChart } from './HistoryChart'
import { useGlobalIndices, useGlobalIndexHistory, useMarketIndices } from '@/hooks/useMarket'
import { useColorScheme } from '@/stores/settings'

/** 区域归属与标签（code → 展示顺序，见 GLOBAL_INDEX_CODES）。 */
const EQUITY_ORDER = ['HSI', 'HSTECH', 'DJIA', 'NDX', 'SPX', 'N225']
const BOND_ORDER = ['US2Y', 'US10Y', 'JP10Y']
const COMMODITY_ORDER = ['GC00Y', 'DXY']
const SPREAD_CODE = 'US2Y10S'
const BOND_CODES = new Set([...BOND_ORDER, SPREAD_CODE])

const TAG_META: Record<string, { tag: string; color: string }> = {
  HSI: { tag: '港股', color: 'gold' },
  HSTECH: { tag: '港股', color: 'gold' },
  DJIA: { tag: '美股', color: 'blue' },
  NDX: { tag: '美股', color: 'blue' },
  SPX: { tag: '美股', color: 'blue' },
  N225: { tag: '日股', color: 'gold' },
  US2Y: { tag: '美债', color: 'blue' },
  US10Y: { tag: '美债', color: 'blue' },
  JP10Y: { tag: '日债', color: 'gold' },
  GC00Y: { tag: '商品', color: 'gold' },
  DXY: { tag: '汇率', color: 'gold' },
}

function SectionHead({ name, sub }: { name: string; sub: string }) {
  return (
    <div className="flex items-baseline gap-3 mb-3">
      <span className="text-[13px] font-semibold text-gray-200">{name}</span>
      <span className="text-[11px] text-gray-600">{sub}</span>
    </div>
  )
}

/** 指数点位千分位（3,845.21）。 */
function fmtIndex(value: number): string {
  return value.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

interface GlobalCardProps {
  quote: GlobalIndexQuote
  selected: boolean
  onSelect: (code: string) => void
}

function GlobalCard({ quote, selected, onSelect }: GlobalCardProps) {
  const meta = TAG_META[quote.indexCode] ?? { tag: '全球', color: 'blue' }
  const isBond = BOND_CODES.has(quote.indexCode)
  return (
    <MacroCard
      name={quote.indexName}
      tag={meta.tag}
      tagColor={meta.color}
      value={
        quote.close === null
          ? '-'
          : isBond
            ? `${quote.close.toFixed(3)}%`
            : fmtIndex(quote.close)
      }
      changePct={quote.changePct}
      active={selected}
      onClick={() => onSelect(quote.indexCode)}
      footer={
        <>
          <span>快照 {quote.tradeDate ?? '-'}</span>
          <span>日K</span>
        </>
      }
    />
  )
}

export function MacroMonitor() {
  useColorScheme()
  const [selectedCode, setSelectedCode] = useState('US10Y')
  const { data: cnIndices } = useMarketIndices()
  const { data: globalIndices } = useGlobalIndices()
  // 利差卡与走势图共用 12 个月缓存
  const { data: spreadHistory } = useGlobalIndexHistory(SPREAD_CODE, 12)

  const byCode = useMemo(() => {
    const map = new Map<string, GlobalIndexQuote>()
    for (const q of globalIndices ?? []) map.set(q.indexCode, q)
    return map
  }, [globalIndices])

  // 2s10s 利差卡（衍生指标：末值 + 较前一日变动，单位 bp）
  const spreadLast = spreadHistory ? spreadHistory[spreadHistory.length - 1] : undefined
  const spreadPrev = spreadHistory ? spreadHistory[spreadHistory.length - 2] : undefined
  const spreadBp = spreadLast ? spreadLast.close * 100 : null
  const spreadDiffBp =
    spreadLast && spreadPrev ? (spreadLast.close - spreadPrev.close) * 100 : null

  const nameFor = (code: string): string => {
    if (code === SPREAD_CODE) return '美债 2s10s 利差'
    return byCode.get(code)?.indexName ?? cnIndices?.find((i) => i.code === code)?.name ?? code
  }
  const isBondChart = BOND_CODES.has(selectedCode)

  return (
    <div className="space-y-6">
      <div>
        <Typography.Title level={4} className="!mb-1">
          宏观指数监测
        </Typography.Title>
        <div className="text-xs text-gray-600">
          投资流程第一站：宏观 → 板块 → 个股 · 指标清单由后台「跟踪指数管理」配置 ·
          数据源：新浪 / 东方财富 / Tushare / 日本财务省 / CME
        </div>
      </div>

      <section>
        <SectionHead name="股指" sub="A 股实时 · 港股收盘 · 美股隔夜" />
        <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
          {(cnIndices ?? []).map((index: IndexQuote) => (
            <MacroCard
              key={index.code}
              name={index.name}
              tag="A股"
              tagColor="red"
              value={fmtIndex(index.price)}
              changePct={index.changePct}
              trend={index.trend}
              active={selectedCode === index.code}
              onClick={() => setSelectedCode(index.code)}
              footer={
                <>
                  <span>实时行情</span>
                  <span>近 30 日</span>
                </>
              }
            />
          ))}
          {EQUITY_ORDER.map((code) => {
            const quote = byCode.get(code)
            if (!quote) return null
            return (
              <GlobalCard
                key={code}
                quote={quote}
                selected={selectedCode === code}
                onSelect={setSelectedCode}
              />
            )
          })}
        </div>
      </section>

      <section>
        <SectionHead name="债券" sub="收益率变动以基点（bp）计 · 利差为衍生指标" />
        <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
          {BOND_ORDER.map((code) => {
            const quote = byCode.get(code)
            if (!quote) return null
            return (
              <GlobalCard
                key={code}
                quote={quote}
                selected={selectedCode === code}
                onSelect={setSelectedCode}
              />
            )
          })}
          <MacroCard
            name="美债 2s10s 利差"
            tag="衍生"
            tagColor="purple"
            value={
              spreadBp === null
                ? '-'
                : `${spreadBp >= 0 ? '+' : ''}${spreadBp.toFixed(1)}bp`
            }
            changePct={spreadDiffBp}
            changeLabel={
              spreadDiffBp === null
                ? '-'
                : `${spreadDiffBp >= 0 ? '+' : ''}${spreadDiffBp.toFixed(1)}bp`
            }
            active={selectedCode === SPREAD_CODE}
            onClick={() => setSelectedCode(SPREAD_CODE)}
            footer={
              <>
                <span>由 2Y/10Y 推算</span>
                <span>日K</span>
              </>
            }
          />
        </div>
      </section>

      <section>
        <SectionHead name="商品与其他" sub="贵金属 / 美元指数 / 能源（规划中）" />
        <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
          {COMMODITY_ORDER.map((code) => {
            const quote = byCode.get(code)
            if (!quote) return null
            return (
              <GlobalCard
                key={code}
                quote={quote}
                selected={selectedCode === code}
                onSelect={setSelectedCode}
              />
            )
          })}
          <GhostCard title="布伦特原油 · 规划中" note="后台登记 + Spider 支持后启用" />
          <GhostCard title="白银 / 更多指标" note="依托跟踪指数管理扩展" />
        </div>
      </section>

      <section>
        <SectionHead name="政策概率" sub="CME FedWatch 期货隐含概率 · 每日更新" />
        <FedWatchSection />
      </section>

      <HistoryChart
        key={selectedCode}
        code={selectedCode}
        name={nameFor(selectedCode)}
        unit={isBondChart ? '%' : ''}
        decimals={isBondChart ? 3 : 2}
      />

      <div className="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-4">
        <Card variant="borderless" title="宏观关联资讯">
          <Empty
            className="py-8"
            description="宏观资讯中心即将上线（迭代 3 接入）"
          />
        </Card>
        <Card variant="borderless" title="决策路径">
          <div className="flex flex-col gap-2.5 text-[13px] text-gray-400">
            <div className="flex items-center gap-2">
              <span className="text-purple-400">① 宏观</span>
              <span className="text-[#5e6ad2]">当前页</span> — 判断大类环境
            </div>
            <div className="flex items-center gap-2">
              <span className="text-purple-400">② 板块</span>
              <Link to="/capital-flow">板块监测</Link> — 定位资金去向
            </div>
            <div className="flex items-center gap-2">
              <span className="text-purple-400">③ 个股</span>
              <Link to="/workbench">顶部搜索个股</Link> — 验证标的走势
            </div>
            <div className="flex items-center gap-2">
              <span className="text-purple-400">④ 分析</span>
              <Link to="/review">每日复盘</Link> — 形成结论
            </div>
          </div>
        </Card>
      </div>
    </div>
  )
}
