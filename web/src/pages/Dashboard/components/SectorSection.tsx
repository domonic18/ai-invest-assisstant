import { Card, Skeleton, Table, Typography } from 'antd'
import { Link } from 'react-router-dom'

import type { SectorOverview } from '@ai-invest/shared'
import { SourceNote } from '@/components/common/SourceNote'
import { useColorScheme, useSettingsStore } from '@/stores/settings'
import { changeColor, fallHex, formatAmount, formatPercent, riseHex } from '@/utils/formatters'

interface SectorSectionProps {
  data?: SectorOverview
  loading: boolean
  /** 查看的是当日且尚未收盘（板块资金收盘后才写入）。 */
  pendingClose?: boolean
  /** 查看的是历史日期，可通过右上角按钮补采。 */
  canBackfill?: boolean
}

const RED_CELL = {
  strong: 'bg-[#3a1a1a] text-red-400',
  mid: 'bg-[#2e1a1a] text-red-300',
  faint: 'bg-[#241818] text-red-200/70',
}
const GREEN_CELL = {
  strong: 'bg-[#1a3a2a] text-green-400',
  mid: 'bg-[#1a2e20] text-green-300',
  faint: 'bg-[#1a2418] text-green-200/70',
}

function heatCellStyle(changePct: number | null): string {
  if (changePct === null) return 'bg-[#1a1d24] text-gray-400'
  const isCn = useSettingsStore.getState().colorScheme === 'cn'
  const palette = (changePct >= 0) === isCn ? RED_CELL : GREEN_CELL
  const abs = Math.abs(changePct)
  if (abs >= 3) return palette.strong
  if (abs >= 1) return palette.mid
  return palette.faint
}

export function SectorSection({ data, loading, pendingClose, canBackfill }: SectorSectionProps) {
  useColorScheme()

  if (loading) {
    return <Skeleton active paragraph={{ rows: 8 }} />
  }
  if (!data || (data.heatmap.length === 0 && data.topInflow.length === 0)) {
    const emptyText = pendingClose
      ? '今日还未收盘，板块资金数据将在收盘后更新'
      : canBackfill
        ? '暂无板块资金数据，可点击右上角「补采数据」获取该日历史数据'
        : '暂无板块资金数据，等待采集任务执行'
    return (
      <section className="space-y-4">
        <Typography.Text className="text-gray-400 text-xs tracking-widest">资金面</Typography.Text>
        <Card variant="borderless" title="板块热力图">
          <div className="text-gray-500 text-sm">{emptyText}</div>
        </Card>
      </section>
    )
  }

  const leadingColumns = [
    { title: '板块', dataIndex: 'sectorName', key: 'sectorName' },
    {
      title: '涨幅',
      dataIndex: 'changePct',
      key: 'changePct',
      align: 'right' as const,
      render: (value: number | null) => (
        <span className={changeColor(value)}>{value != null ? formatPercent(value) : '-'}</span>
      ),
    },
    { title: '涨停数', dataIndex: 'limitUpCount', key: 'limitUpCount', align: 'right' as const },
    {
      title: '资金净流入',
      dataIndex: 'mainNetInflow',
      key: 'mainNetInflow',
      align: 'right' as const,
      render: (value: number | null) => (
        <span className={changeColor(value)}>{formatAmount(value)}</span>
      ),
    },
    {
      title: '领涨龙头',
      dataIndex: 'topStockNames',
      key: 'topStockNames',
      render: (names: string[]) => names.join(' · ') || '-',
    },
  ]

  return (
    <section className="space-y-4">
      <Typography.Text className="text-gray-400 text-xs tracking-widest">资金面</Typography.Text>

      <Card variant="borderless" title="板块热力图" extra={<span className="text-xs text-gray-500">行业板块涨跌分布</span>}>
        <div className="grid grid-cols-3 sm:grid-cols-5 gap-2">
          {data.heatmap.map((cell) => (
            <div
              key={cell.sectorName}
              className={`rounded p-2 text-center text-xs leading-5 ${heatCellStyle(cell.changePct)}`}
            >
              {cell.sectorName}
              <br />
              {cell.changePct != null ? formatPercent(cell.changePct) : '-'}
            </div>
          ))}
        </div>
        <SourceNote>东方财富板块资金流（备用渠道： 同花顺）</SourceNote>
      </Card>

      <Card
        variant="borderless"
        title="板块资金净流入/流出 TOP5"
        extra={<Link to="/capital-flow" className="text-xs">查看完整 →</Link>}
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <div className="text-xs font-semibold mb-2" style={{ color: riseHex() }}>↑ 主力净流入</div>
            <div className="space-y-1">
              {data.topInflow.map((item) => (
                <div
                  key={item.sectorName}
                  className="flex justify-between text-xs rounded px-2 py-1.5"
                  style={{ backgroundColor: `${riseHex()}0d` }}
                >
                  <span>{item.sectorName}</span>
                  <span className="font-medium" style={{ color: riseHex() }}>+{formatAmount(item.mainNetInflow)}</span>
                </div>
              ))}
              {data.topInflow.length === 0 && <div className="text-xs text-gray-500">无净流入板块</div>}
            </div>
          </div>
          <div>
            <div className="text-xs font-semibold mb-2" style={{ color: fallHex() }}>↓ 主力净流出</div>
            <div className="space-y-1">
              {data.topOutflow.map((item) => (
                <div
                  key={item.sectorName}
                  className="flex justify-between text-xs rounded px-2 py-1.5"
                  style={{ backgroundColor: `${fallHex()}0d` }}
                >
                  <span>{item.sectorName}</span>
                  <span className="font-medium" style={{ color: fallHex() }}>{formatAmount(item.mainNetInflow)}</span>
                </div>
              ))}
              {data.topOutflow.length === 0 && <div className="text-xs text-gray-500">无净流出板块</div>}
            </div>
          </div>
        </div>
      </Card>

      <Card variant="borderless" title="领涨板块">
        <Table
          dataSource={data.leading}
          columns={leadingColumns}
          rowKey="sectorName"
          pagination={false}
          size="small"
          scroll={{ x: 560 }}
        />
        <SourceNote>东方财富板块资金流 · 涨停数来自东方财富涨停股池</SourceNote>
      </Card>
    </section>
  )
}
