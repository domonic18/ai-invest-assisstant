import { Card, Tag, Typography } from 'antd'
import { Link, useParams } from 'react-router-dom'

import { IndexChartPanel } from '@/pages/Dashboard/components/IndexChartPanel'
import { useGlobalIndices, useIndexKline } from '@/hooks/useMarket'
import { useColorScheme } from '@/stores/settings'
import { changeColor, formatPercent } from '@/utils/formatters'

import { GlobalIndexKlinePanel } from './GlobalIndexKlinePanel'

/** 有分钟线数据的指数（对齐后端 INDEX_CODES），其余 K 线标的隐藏分时。 */
const INTRADAY_CODES = new Set(['sh000001', 'sz399001', 'sz399006', 'sh000688'])
/** K 线扩展标的中无 sh/sz 前缀的（富时A50，东财日 K）。 */
const KLINE_EXTRA_CODES = new Set(['CN00Y'])
/** 债券与利差：详情走势图按收益率（%）展示。 */
const BOND_CODES = new Set(['US2Y', 'US10Y', 'US30Y', 'JP10Y', 'US2Y10S'])

function isKlineCode(code: string): boolean {
  return /^(sh|sz)/.test(code) || KLINE_EXTRA_CODES.has(code)
}

export function IndexDetail() {
  useColorScheme()
  const { code = '' } = useParams()
  const klineBranch = isKlineCode(code)

  const { data: kline } = useIndexKline(code, 'daily', klineBranch)
  const { data: globalIndices } = useGlobalIndices()

  const globalQuote = klineBranch ? undefined : globalIndices?.find((g) => g.indexCode === code)
  const name = klineBranch ? (kline?.name ?? code) : (globalQuote?.indexName ?? code)
  const isBond = BOND_CODES.has(code)

  return (
    <div className="space-y-4">
      <div className="flex items-baseline gap-3 flex-wrap">
        <Typography.Title level={4} className="!mb-0">
          {name}
        </Typography.Title>
        <Tag className="!mr-0 font-mono">{code}</Tag>
        <Link to="/macro-monitor" className="text-xs">
          ← 宏观指数监测
        </Link>
      </div>

      {!klineBranch && globalQuote && (
        <div className="flex items-baseline gap-3">
          <span className="text-2xl font-semibold font-mono">
            {globalQuote.close != null ? globalQuote.close.toFixed(isBond ? 3 : 2) : '-'}
            {isBond ? '%' : ''}
          </span>
          <span
            className={`text-sm font-mono font-semibold ${changeColor(globalQuote.changePct)}`}
          >
            {globalQuote.changePct != null ? formatPercent(globalQuote.changePct) : '-'}
          </span>
          <span className="text-xs text-gray-500 ml-auto font-mono">
            快照 {globalQuote.tradeDate ?? '-'}
          </span>
        </div>
      )}

      <Card variant="borderless">
        {klineBranch ? (
          <IndexChartPanel code={code} noIntraday={!INTRADAY_CODES.has(code)} />
        ) : (
          <GlobalIndexKlinePanel code={code} decimals={isBond ? 3 : 2} />
        )}
      </Card>
    </div>
  )
}
