/**
 * 「Agent 自选」卡片（自选页 agent 分组迁入模拟管理）：AI 选股清单复用
 * 「我的自选」行样式（D28：名称/代号 + 分时缩略图 + 现价/涨跌幅，红涨绿跌
 * 走 scheme-aware helpers）+ AI 置信度标签与选入依据；人工移出全局生效，
 * 次日不重选。行情 per-code 拉取（quote + 当日分时）。
 */
import { MinusCircleOutlined } from '@ant-design/icons'
import { Button, Card, Empty, Popconfirm, Tag, Tooltip } from 'antd'
import { useNavigate } from 'react-router-dom'

import type { ApiAgentWatchlistSelectionItem } from '@ai-invest/shared'

import { IntradaySpark } from '@/components/charts/IntradaySpark'
import {
  useRemoveTradingAgentSelection,
  useTradingAgentSelections,
} from '@/hooks/useTradingAgent'
import { useStockIntraday, useStockQuote } from '@/hooks/useStocks'
import { useColorScheme } from '@/stores/settings'
import { changeColor, formatPercent } from '@/utils/formatters'

import { useAgentKey } from './agentKeyContext'

function SelectionRow({ item }: { item: ApiAgentWatchlistSelectionItem }) {
  const navigate = useNavigate()
  const agentKey = useAgentKey()
  const remove = useRemoveTradingAgentSelection(agentKey)
  useColorScheme()
  const { data: quote } = useStockQuote(item.stockCode)
  const { data: intraday } = useStockIntraday(item.stockCode)

  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">
      <div className="flex items-center gap-3">
        <button
          type="button"
          className="min-w-0 flex-1 cursor-pointer text-left"
          onClick={() => navigate(`/stock/${item.stockCode}`)}
        >
          <div className="truncate text-sm text-gray-200">{quote?.name ?? item.stockCode}</div>
          <div className="text-xs text-gray-500 font-mono">{item.stockCode}</div>
        </button>
        <IntradaySpark
          points={intraday?.points.map((point) => point.price)}
          changePct={quote?.changePct ?? null}
          width={64}
        />
        <div className="w-[72px] shrink-0 text-right">
          <div className="font-mono text-sm text-gray-200">
            {quote?.price != null ? quote.price.toFixed(2) : '-'}
          </div>
          <div className={`text-xs font-mono ${changeColor(quote?.changePct)}`}>
            {quote?.changePct != null ? formatPercent(quote.changePct) : '-'}
          </div>
        </div>
        {item.confidence != null && (
          <Tooltip title="AI 选股置信度，由选股模型输出">
            <Tag color="geekblue" className="!mr-0">
              置信度 {(item.confidence * 100).toFixed(0)}%
            </Tag>
          </Tooltip>
        )}
        <Popconfirm
          title="移出 AI 选股"
          description="移出后全局生效，Agent 次日不会再选入该股。确定移出？"
          okText="移出"
          cancelText="取消"
          onConfirm={() => remove.mutate(item.id)}
        >
          <Button
            type="text"
            size="small"
            danger
            icon={<MinusCircleOutlined />}
            aria-label={`移出 ${item.stockCode}`}
          />
        </Popconfirm>
      </div>
      <div className="mt-1 flex items-center gap-2 text-xs text-gray-500">
        <Tag color="geekblue" className="!mr-0">
          AI 选入 {item.tradeDate}
        </Tag>
        <Tooltip title={item.reason} placement="bottomLeft">
          <div className="min-w-0 flex-1 truncate text-gray-300">{item.reason}</div>
        </Tooltip>
      </div>
    </div>
  )
}

export function AgentSelectionsPanel() {
  const agentKey = useAgentKey()
  const { data: group, isLoading } = useTradingAgentSelections(agentKey)
  const selections = group?.items ?? []

  return (
    <Card size="small" title={group?.name ?? 'Agent 自选'}>
      {isLoading ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="加载中…"
        />
      ) : selections.length === 0 ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="暂无选股（每个交易日 19:00 自动生成，也可在对话中制定）"
        />
      ) : (
        <div className="space-y-2">
          {selections.map((item) => (
            <SelectionRow key={item.id} item={item} />
          ))}
        </div>
      )}
    </Card>
  )
}
