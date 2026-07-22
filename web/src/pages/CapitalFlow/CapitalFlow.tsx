import { Card, Empty, Radio, Segmented, Spin, Typography } from 'antd'
import { useEffect, useState } from 'react'

import type { SectorType } from '@/api/fundFlow'
import { useSectorFundFlowTrend } from '@/hooks/useFundFlow'
import { useColorScheme } from '@/stores/settings'

import { SectorFlowAreaChart } from './SectorFlowAreaChart'
import { SectorRankBarChart } from './SectorRankBarChart'

const RANGE_OPTIONS = [
  { label: '近 30 个交易日', value: 30 },
  { label: '近 60 个交易日', value: 60 },
  { label: '近 120 个交易日', value: 120 },
]

const SECTOR_TYPE_OPTIONS = [
  { label: '行业板块', value: 'industry' },
  { label: '概念板块', value: 'concept' },
]

export function CapitalFlow() {
  useColorScheme()
  const [sectorType, setSectorType] = useState<SectorType>('industry')
  const [days, setDays] = useState(60)
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const { data, isLoading, error } = useSectorFundFlowTrend(sectorType, days)

  // 切换板块类型/范围导致数据更新后，默认选中最后一天
  useEffect(() => {
    if (data && data.dates.length > 0) {
      setSelectedDate((prev) =>
        prev && data.dates.includes(prev)
          ? prev
          : data.dates[data.dates.length - 1],
      )
    } else {
      setSelectedDate(null)
    }
  }, [data])

  const isEmpty = error || !data || data.dates.length === 0

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Typography.Title level={4} className="!mb-0">
          资金流向
        </Typography.Title>
        <div className="flex items-center gap-3">
          <Segmented
            options={SECTOR_TYPE_OPTIONS}
            value={sectorType}
            onChange={(value) => setSectorType(value as SectorType)}
            size="small"
          />
          <Radio.Group
            options={RANGE_OPTIONS}
            value={days}
            onChange={(e) => setDays(e.target.value as number)}
            optionType="button"
            size="small"
          />
        </div>
      </div>
      {isLoading ? (
        <Card variant="borderless">
          <div className="flex justify-center py-24">
            <Spin />
          </div>
        </Card>
      ) : isEmpty ? (
        <Card variant="borderless">
          <Empty
            className="py-16"
            description="暂无板块资金流向数据（采集任务交易日 17:30 运行后可用）"
          />
        </Card>
      ) : (
        <>
          <Card
            variant="borderless"
            title="板块资金流向（上=净流入 / 下=净流出，单位：亿元）"
          >
            {data.dates.length < 2 ? (
              <Empty
                className="py-16"
                description="趋势图需至少 2 个交易日数据，每日 17:30 采集积累后自动展示"
              />
            ) : (
              <SectorFlowAreaChart
                data={data}
                selectedDate={selectedDate}
                onSelectDate={setSelectedDate}
              />
            )}
          </Card>
          <Card
            variant="borderless"
            title={`当日板块排名${selectedDate ? `（${selectedDate}）` : ''}（单位：亿元）`}
          >
            <SectorRankBarChart
              data={data}
              selectedDate={selectedDate}
              onSelectDate={setSelectedDate}
            />
          </Card>
        </>
      )}
    </div>
  )
}
