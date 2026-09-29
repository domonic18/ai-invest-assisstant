/**
 * 执行动态卡片（批次 8 PR-3）：盘中自主执行逐 tick 观测留痕
 * （paper_trade_exec_observation）的人工核查窗口，影子期评审入口。
 *
 * 数据源 admin GET /trading-agent/{agentKey}/observations（分页 + 恒全天口径
 * summary）；默认只看显著事件（L0 非无动作或存在抑制原因），Segmented 切
 * 「全部」逐 tick。用户未显式选日时后端解析为最近有观测日并 60s 轮询跟进
 * 盘中新落行，选历史日期不轮询。尾盘强检行（window='tail_check'）与盘中行
 * 同列（无计划关联）；影子判断行打金色「影子」badge；标的可点跳个股详情。
 */
import { Card, Empty, Pagination, Segmented, Space, Spin, Tag } from 'antd'
import type { Dayjs } from 'dayjs'
import { useState } from 'react'

import type { ApiTradingAgentObservationSummary } from '@ai-invest/shared'

import { MarkedDatePicker } from '@/components/common/MarkedDatePicker'
import { useAgentKey } from './agentKeyContext'
import { ACTION_META, SUPPRESSION_META, VERDICT_META } from './observationMeta'
import { ObservationLegend } from './observationLegend'
import { ObservationRow } from './ObservationRow'
import { useTradingAgentObservations } from '@/hooks/useTradingAgent'
import { DATE_FORMAT } from '@/utils/formatters'

/** 顶部统计条：全天口径 tick 总数 + 判定/动作/抑制分布（不受显著过滤影响）。 */
function SummaryStrip({ summary }: { summary: ApiTradingAgentObservationSummary }) {
  const chips: Array<{ key: string; label: string; color?: string }> = [
    { key: 'total', label: `tick ${summary.totalTicks}` },
    { key: 'significant', label: `显著 ${summary.significantTicks}` },
  ]
  for (const [verdict, count] of Object.entries(summary.l0VerdictCounts)) {
    chips.push({
      key: `v-${verdict}`,
      label: `${VERDICT_META[verdict]?.label ?? verdict} ${count}`,
    })
  }
  for (const [action, count] of Object.entries(summary.actionCounts)) {
    chips.push({ key: `a-${action}`, label: `${ACTION_META[action]?.label ?? action} ${count}` })
  }
  for (const [reason, count] of Object.entries(summary.suppressionCounts)) {
    chips.push({
      key: `s-${reason}`,
      label: `${SUPPRESSION_META[reason] ?? reason} ${count}`,
    })
  }
  return (
    <div className="flex flex-wrap gap-1.5">
      {chips.map((chip) => (
        <Tag key={chip.key} className="!mr-0">
          {chip.label}
        </Tag>
      ))}
    </div>
  )
}

export function ExecutionTab() {
  const agentKey = useAgentKey()
  const [selectedDate, setSelectedDate] = useState<Dayjs | null>(null)
  const [significant, setSignificant] = useState(true)
  const [page, setPage] = useState(1)
  const tradeDate = selectedDate?.format(DATE_FORMAT)
  const { data, isLoading } = useTradingAgentObservations(agentKey, {
    tradeDate,
    significant,
    page,
    isLatest: selectedDate == null,
  })

  const changeSignificant = (value: string | number) => {
    setSignificant(value === 'significant')
    setPage(1)
  }

  return (
    <Card
      size="small"
      title={data ? `${data.tradeDate} 执行动态` : '执行动态'}
      extra={
        <div className="flex items-center gap-2">
          <ObservationLegend />
          <Segmented
            size="small"
            value={significant ? 'significant' : 'all'}
            onChange={changeSignificant}
            options={[
              { label: '显著事件', value: 'significant' },
              { label: '全部', value: 'all' },
            ]}
          />
          <MarkedDatePicker
            value={selectedDate}
            onChange={(value) => {
              setSelectedDate(value)
              setPage(1)
            }}
            allowClear
            size="small"
            placeholder="最近有观测日"
          />
        </div>
      }
    >
      {isLoading ? (
        <div className="flex justify-center py-8">
          <Spin />
        </div>
      ) : !data ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无观测数据" />
      ) : (
        <Space direction="vertical" size="small" className="w-full">
          <SummaryStrip summary={data.summary} />
          {data.items.length === 0 ? (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={
                significant
                  ? '该日无显著事件（可切换「全部」查看逐 tick 留痕）'
                  : '该日无观测留痕（执行器仅在交易时段运行，shadow 模式不下单）'
              }
            />
          ) : (
            <>
              {data.items.map((item) => (
                <ObservationRow key={item.id} item={item} />
              ))}
              <div className="flex justify-end">
                <Pagination
                  current={data.page}
                  pageSize={data.pageSize}
                  total={data.total}
                  onChange={setPage}
                  showSizeChanger={false}
                  showTotal={(total) => `共 ${total} 条`}
                />
              </div>
            </>
          )}
        </Space>
      )}
    </Card>
  )
}
