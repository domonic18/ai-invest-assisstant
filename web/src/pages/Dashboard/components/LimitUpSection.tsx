import { useQueryClient } from '@tanstack/react-query'
import { Button, Card, message, Skeleton, Tag, Typography } from 'antd'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import type { LimitUpData, LimitUpStock } from '@ai-invest/shared'
import { IntradaySpark } from '@/components/charts/IntradaySpark'
import { SourceNote } from '@/components/common/SourceNote'
import { useLimitUpIntraday } from '@/hooks/useMarket'
import { usePageAssistantResult } from '@/hooks/usePageAssistantResult'
import { useAssistantStore } from '@/stores/assistant'
import { useColorScheme } from '@/stores/settings'
import {
  changeColor,
  changeHex,
  formatAmount,
  formatPercent,
  formatSealTime,
  riseColorSoft,
  riseHex,
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

function boardColor(boards: number): string {
  switch (boards) {
    case 6:
      return riseHex()
    case 5:
    case 4:
      return '#d29922'
    default:
      return '#5e6ad2'
  }
}

function SealBadge({ item }: { item: LimitUpStock }) {
  const boards = item.consecutiveBoards ?? 0
  const boardText = boards >= 2 ? `${boards}板` : '首板'
  const sealIcon = item.sealType === '一字板' ? '一' : item.sealType === 'T字板' ? 'T' : null
  return (
    <span className="flex items-center gap-1 shrink-0">
      <span
        className="rounded px-1.5 py-0.5 text-xs font-bold text-white whitespace-nowrap"
        style={{ background: boardColor(boards) }}
      >
        {boardText}
      </span>
      {sealIcon && (
        <span
          className="w-5 h-5 rounded text-center leading-5 text-xs font-bold text-white"
          style={{ background: item.sealType === '一字板' ? riseHex() : '#d29922' }}
          title={item.sealType ?? undefined}
        >
          {sealIcon}
        </span>
      )}
    </span>
  )
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
  const panelOpen = useAssistantStore((s) => s.open)
  const { data: intraday } = useLimitUpIntraday(tradeDate, (data?.total ?? 0) > 0)

  // 生成入口走 AI 助手侧边栏：agent 按 SKILL.md 工具取数分析，过程全程可见，
  // 完成后经 pageResult 事件回写刷新本区
  const handleGenerate = (regenerate: boolean) => {
    setGenerating(true)
    useAssistantStore
      .getState()
      .sendQuestion(
        `请${regenerate ? '重新' : ''}生成 ${tradeDate ?? '最近交易日'} 的涨停板块归因`
      )
  }

  usePageAssistantResult('limit_up_attribution.complete', () => {
    setGenerating(false)
    void queryClient.invalidateQueries({ queryKey: ['market', 'limit-up', tradeDate] })
    message.success('AI 归因已生成，已刷新')
    return true
  })

  // 侧边栏关闭（含 agent 中途失败被放弃）时解除本区的进行中提示
  useEffect(() => {
    if (!panelOpen) setGenerating(false)
  }, [panelOpen])

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
                <Link to={`/stock/${item.stockCode}`} className="flex-1 font-medium truncate">
                  {item.stockName}
                </Link>
                <span className="hidden sm:inline font-mono text-xs text-gray-500">{item.stockCode}</span>
                <Tag color="default" className="hidden sm:inline-block">{item.industry ?? '未分类'}</Tag>
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
          <span className="flex flex-wrap items-center justify-end gap-2">
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
                {generating ? 'AI 归因中，请留意侧边栏助手…' : 'AI 归因'}
              </Button>
            )}
          </span>
        }
      >
        <div className="space-y-4">
          {data.groups.map((group) => (
            <div key={group.name}>
              <div
                className="rounded px-2.5 py-1.5 mb-2"
                style={{ backgroundColor: `${riseHex()}1a` }}
              >
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <span className={`text-sm font-semibold ${riseColorSoft()}`}>{group.name}</span>
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
                    <span className="hidden sm:inline w-16 font-mono text-xs text-gray-500">
                      {item.stockCode}
                    </span>
                    <span className="hidden sm:inline w-14 text-right font-mono text-xs text-gray-400">
                      {formatSealTime(item.lastSealTime ?? item.firstSealTime)}
                    </span>
                    <span className="hidden sm:inline-flex">
                      <IntradaySpark
                        points={intraday?.series[item.stockCode]}
                        changePct={item.changePct}
                      />
                    </span>
                    <ThemeTags item={item} />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
        <SourceNote>
          {data.aiGenerated
            ? '东方财富涨停股池 · 时间为最终封板时间 · 题材分组与涨停原因由 AI 基于当日行情、板块资金与新闻归纳，仅供参考 · 图标 一=一字板（开盘涨停全天未开板），T=T字板（开盘涨停盘中打开后回封）'
            : '东方财富涨停股池 · 时间为最终封板时间 · 按所属行业分组 · 板块涨跌幅/主力净流入来自板块资金流 · 图标 一=一字板（开盘涨停全天未开板），T=T字板（开盘涨停盘中打开后回封）'}
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
