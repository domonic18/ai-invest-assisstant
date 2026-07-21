import { useQueryClient } from '@tanstack/react-query'
import { Button, Card, message, Skeleton, Tag, Typography } from 'antd'
import axios from 'axios'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import type { LimitUpData, LimitUpStock } from '@ai-invest/shared'
import { generateLimitUpAttribution } from '@/api/market'
import { IntradaySpark } from '@/components/charts/IntradaySpark'
import { SourceNote } from '@/components/common/SourceNote'
import { useLimitUpIntraday } from '@/hooks/useMarket'
import { useColorScheme } from '@/stores/settings'
import {
  changeColor,
  changeHex,
  formatAmount,
  formatPercent,
  formatSealTime,
} from '@/utils/formatters'

interface LimitUpSectionProps {
  data?: LimitUpData
  loading: boolean
  /** 查看的是当日且尚未收盘（涨停池收盘后才写入）。 */
  pendingClose?: boolean
  /** 查看的是历史日期，可通过右上角按钮补采。 */
  canBackfill?: boolean
  /** 当前查看的交易日期（不传表示最近交易日），用于触发 AI 归因。 */
  tradeDate?: string
}

const BOARD_COLORS: Record<number, string> = {
  6: '#f85149',
  5: '#d29922',
  4: '#d29922',
}

function boardColor(boards: number): string {
  return BOARD_COLORS[boards] ?? '#5e6ad2'
}

function SealBadge({ item }: { item: LimitUpStock }) {
  const boards = item.consecutiveBoards ?? 0
  const boardText = boards >= 2 ? `${boards}板` : '首板'
  const prefix = item.sealType === '一字板' ? '一字' : item.sealType === 'T字板' ? 'T' : null
  const color = prefix ? '#f85149' : boardColor(boards)
  return (
    <span
      className="rounded px-1.5 py-0.5 text-xs font-bold text-white whitespace-nowrap"
      style={{ background: color }}
    >
      {prefix ? `${prefix}·${boardText}` : boardText}
    </span>
  )
}

function errorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: string } | undefined)?.detail
    return detail ?? err.message
  }
  return err instanceof Error ? err.message : '操作失败'
}

function ThemeTags({ item }: { item: LimitUpStock }) {
  if (item.themes.length === 0) {
    return (
      <Tag color="default" className="ml-auto">
        {item.industry ?? '未分类'}
      </Tag>
    )
  }
  return (
    <span className="ml-auto flex items-center gap-1">
      {item.themes.slice(0, 2).map((theme) => (
        <Tag key={theme} color="red">
          {theme}
        </Tag>
      ))}
    </span>
  )
}

export function LimitUpSection({
  data,
  loading,
  pendingClose,
  canBackfill,
  tradeDate,
}: LimitUpSectionProps) {
  useColorScheme()
  const queryClient = useQueryClient()
  const [generating, setGenerating] = useState(false)
  const { data: intraday } = useLimitUpIntraday(tradeDate, (data?.total ?? 0) > 0)

  const handleGenerate = async (regenerate: boolean) => {
    setGenerating(true)
    try {
      const result = await generateLimitUpAttribution(regenerate, tradeDate)
      queryClient.setQueryData(['market', 'limit-up', tradeDate], result)
      message.success(regenerate ? '已重新归因' : 'AI 归因完成')
    } catch (err) {
      message.error(errorMessage(err))
    } finally {
      setGenerating(false)
    }
  }

  if (loading) {
    return <Skeleton active paragraph={{ rows: 6 }} />
  }
  if (!data || data.total === 0) {
    const emptyText = pendingClose
      ? '今日还未收盘，涨停与连板数据将在收盘后更新'
      : canBackfill
        ? '暂无涨停数据，可点击右上角「补采数据」获取该日历史数据'
        : '暂无涨停数据，等待采集任务执行'
    return (
      <Card variant="borderless" title="连板天梯">
        <div className="text-gray-500 text-sm">{emptyText}</div>
      </Card>
    )
  }

  return (
    <>
      <Card
        variant="borderless"
        title="连板天梯"
        extra={<span className="text-xs text-gray-500">当日最高 {data.maxBoards ?? '-'} 板</span>}
      >
        <div className="space-y-1.5">
          {data.ladder.map((item) => {
            const boards = item.consecutiveBoards ?? 0
            return (
              <div
                key={item.stockCode}
                className="flex items-center gap-3 rounded px-2 py-1.5 bg-[#1a1d24]"
                style={{ borderLeft: `3px solid ${boardColor(boards)}` }}
              >
                <span
                  className="w-6 h-6 rounded text-center leading-6 text-xs font-bold text-white"
                  style={{ background: boardColor(boards) }}
                >
                  {boards}
                </span>
                <Link to={`/stock/${item.stockCode}`} className="flex-1 font-medium">
                  {item.stockName}
                </Link>
                <span className="font-mono text-xs text-gray-500">{item.stockCode}</span>
                <Tag color="default">{item.industry ?? '未分类'}</Tag>
                <span className={`text-sm font-medium ${changeColor(item.changePct)}`}>
                  {item.changePct != null ? formatPercent(item.changePct) : '-'}
                </span>
              </div>
            )
          })}
        </div>
        <SourceNote>
          东方财富 · 仅展示 ≥2 板个股 · 涨停 {data.total} 家 · 首板 {data.firstBoard} · 连板 {data.continuous}
        </SourceNote>
      </Card>

      <Card
        variant="borderless"
        title="涨停复盘"
        extra={
          <span className="flex items-center gap-2">
            <span className="text-xs text-gray-400">
              共 {data.total} 只涨停 · 首板 {data.firstBoard} · 连板 {data.continuous}
            </span>
            {data.aiGenerated ? (
              <>
                <Tag color="purple" className="!mr-0">
                  AI
                </Tag>
                <Button
                  size="small"
                  loading={generating}
                  onClick={() => handleGenerate(true)}
                >
                  重新归因
                </Button>
              </>
            ) : (
              <Button
                size="small"
                type="primary"
                ghost
                loading={generating}
                onClick={() => handleGenerate(false)}
              >
                {generating ? 'AI 归因中，通常需要 10-30 秒…' : 'AI 归因'}
              </Button>
            )}
          </span>
        }
      >
        <div className="space-y-4">
          {data.groups.map((group) => (
            <div key={group.name}>
              <div className="rounded bg-red-500/10 px-2.5 py-1.5 mb-2">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <span className="text-sm font-semibold text-red-400">{group.name}</span>
                  {group.changePct != null && (
                    <span
                      className="text-xs font-medium"
                      style={{ color: changeHex(group.changePct) }}
                    >
                      {formatPercent(group.changePct)}
                    </span>
                  )}
                  {group.mainNetInflow != null && (
                    <span className="text-xs text-gray-400">
                      主力净流入 {formatAmount(group.mainNetInflow)}
                    </span>
                  )}
                  <span className="text-xs text-gray-500 ml-auto">
                    {group.count} 家涨停
                  </span>
                </div>
                {group.reason && (
                  <div className="text-xs text-gray-400 mt-1">{group.reason}</div>
                )}
              </div>
              <div className="space-y-1">
                {group.items.map((item) => (
                  <div
                    key={item.stockCode}
                    className="flex items-center gap-2.5 rounded px-2 py-1.5 bg-[#1a1d24]"
                  >
                    <SealBadge item={item} />
                    <Link
                      to={`/stock/${item.stockCode}`}
                      className="w-24 truncate font-medium text-sm"
                    >
                      {item.stockName}
                    </Link>
                    <span className="w-16 font-mono text-xs text-gray-500">
                      {item.stockCode}
                    </span>
                    <span className="w-14 text-right font-mono text-xs text-gray-400">
                      {formatSealTime(item.firstSealTime)}
                    </span>
                    <IntradaySpark
                      points={intraday?.series[item.stockCode]}
                      changePct={item.changePct}
                    />
                    <ThemeTags item={item} />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
        <SourceNote>
          {data.aiGenerated
            ? '东方财富涨停股池 · 题材分组与涨停原因由 AI 基于当日行情、板块资金与新闻归纳，仅供参考 · 一字=开盘涨停全天未开板，T=开盘涨停盘中打开后回封'
            : '东方财富涨停股池 · 按所属行业分组 · 板块涨跌幅/主力净流入来自板块资金流 · 一字=开盘涨停全天未开板，T=开盘涨停盘中打开后回封'}
        </SourceNote>
      </Card>
    </>
  )
}

export function LimitUpSectionTitle() {
  return (
    <Typography.Text className="text-gray-400 text-xs tracking-widest">
      涨停与连板
    </Typography.Text>
  )
}
