import { Skeleton } from 'antd'

import type { GlobalIndexQuote, IndexQuote } from '@ai-invest/shared'
import { useColorScheme } from '@/stores/settings'
import { changeHex, formatPercent } from '@/utils/formatters'

interface IndexStripProps {
  indices?: IndexQuote[]
  globalIndices?: GlobalIndexQuote[]
  loading?: boolean
}

interface Tile {
  key: string
  name: string
  value: number | null
  changePct: number | null
}

/** 页首指标横条：A 股跟踪指数 + 全球指标各一排小卡。 */
export function IndexStrip({ indices, globalIndices, loading }: IndexStripProps) {
  useColorScheme()

  if (loading) {
    return <Skeleton active paragraph={{ rows: 2 }} />
  }

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
  if (!tiles.length) return null

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 xl:grid-cols-8 gap-2.5">
      {tiles.map((tile) => (
        <div
          key={tile.key}
          className="rounded-lg border border-gray-800 bg-[#111318] px-3.5 py-3 min-w-0"
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
        </div>
      ))}
    </div>
  )
}
