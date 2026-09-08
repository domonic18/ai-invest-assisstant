import { Empty, Spin } from 'antd'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import type { GlobalIndexQuote, IndexQuote } from '@ai-invest/shared'
import { useColorScheme } from '@/stores/settings'
import { changeHex, formatPercent } from '@/utils/formatters'

import { FoldCard } from './FoldCard'

interface IndexStripProps {
  indices?: IndexQuote[]
  globalIndices?: GlobalIndexQuote[]
  loading?: boolean
  className?: string
  stretch?: boolean
}

interface Tile {
  key: string
  name: string
  value: number | null
  changePct: number | null
}

/** 指数 tab 分组（口径与宏观监测页四分区一致）；未映射的全球代码落「其他」。 */
const ASHARE_TAB = 'A股'
const GLOBAL_TAB_CODES: Record<string, string[]> = {
  全球股指: ['HSI', 'HSTECH', 'DJIA', 'NDX', 'SPX', 'N225'],
  债券: ['US2Y', 'US10Y', 'US30Y', 'JP10Y'],
  商品: ['GC00Y', 'B00Y'],
  汇率: ['DXY', 'USDCNY', 'USDCNH', 'USDJPY', 'USDEUR'],
}
const OTHER_TAB = '其他'
const TAB_ORDER = [ASHARE_TAB, ...Object.keys(GLOBAL_TAB_CODES), OTHER_TAB]

function tabOf(tile: Tile): string {
  if (/^(sh|sz)/.test(tile.key)) return ASHARE_TAB
  for (const [tab, codes] of Object.entries(GLOBAL_TAB_CODES)) {
    if (codes.includes(tile.key)) return tab
  }
  return OTHER_TAB
}

/** 指数快览卡：tab 分组的 A 股/全球指标，点击进入指数详情。 */
export function IndexStrip({
  indices,
  globalIndices,
  loading,
  className,
  stretch,
}: IndexStripProps) {
  useColorScheme()
  const [tab, setTab] = useState<string>(ASHARE_TAB)

  const tiles: Tile[] = [
    ...(indices ?? []).map<Tile>((i) => ({
      key: i.code,
      name: i.name,
      value: i.price,
      changePct: i.changePct,
    })),
    ...(globalIndices ?? []).map<Tile>((g) => ({
      key: g.indexCode,
      name: g.indexName,
      value: g.close,
      changePct: g.changePct,
    })),
  ]

  const byTab = new Map<string, Tile[]>()
  for (const tile of tiles) {
    const group = tabOf(tile)
    byTab.set(group, [...(byTab.get(group) ?? []), tile])
  }
  const tabs = TAB_ORDER.filter((name) => byTab.has(name))
  const activeTab = byTab.has(tab) ? tab : (tabs[0] ?? ASHARE_TAB)
  const shown = byTab.get(activeTab) ?? []

  return (
    <FoldCard
      title="市场指数"
      extra={
        tabs.length > 1 ? (
          <div className="flex items-center gap-0.5">
            {tabs.map((name) => {
              const active = name === activeTab
              return (
                <button
                  key={name}
                  type="button"
                  onClick={() => setTab(name)}
                  className={`rounded px-1.5 py-px text-xs leading-5 transition-colors ${
                    active
                      ? 'bg-white/8 text-gray-200'
                      : 'text-gray-500 hover:text-gray-300'
                  }`}
                >
                  {name}
                </button>
              )
            })}
          </div>
        ) : undefined
      }
      className={className}
      stretch={stretch}
    >
      {loading ? (
        <div className="flex justify-center py-6">
          <Spin />
        </div>
      ) : !tiles.length ? (
        <Empty description="暂无指数数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <div className="grid [grid-template-columns:repeat(auto-fill,minmax(120px,1fr))] gap-2.5 content-start">
          {shown.map((tile) => (
            <Link
              key={tile.key}
              to={`/index/${tile.key}`}
              title={`查看 ${tile.name} 详情`}
              className="rounded-lg border border-gray-800 bg-[#181a21] px-3 py-2.5 min-w-0 transition-colors hover:border-gray-600"
            >
              <div className="text-[11px] text-gray-500 truncate" title={tile.name}>
                {tile.name}
              </div>
              <div className="font-mono text-base font-bold my-0.5">
                {tile.value != null
                  ? tile.value.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
                  : '-'}
              </div>
              <div
                className="text-[11px] font-semibold font-mono"
                style={{ color: changeHex(tile.changePct) }}
              >
                {tile.changePct != null ? formatPercent(tile.changePct) : '-'}
              </div>
            </Link>
          ))}
        </div>
      )}
    </FoldCard>
  )
}
