import { DatePicker } from 'antd'
import type { DatePickerProps } from 'antd'
import dayjs, { type Dayjs } from 'dayjs'
import { useMemo } from 'react'

import { DATE_FORMAT } from '@/utils/formatters'

interface MarkedDatePickerProps extends DatePickerProps {
  /** 已生成分析/检测的 ISO 日期（升序不限），日历面板以圆点标记。 */
  markedDates?: string[]
}

/** 周末与未来日期不可选；各 AI 日期选择器对非交易日的呈现保持一致。 */
function defaultDisabledDate(current: Dayjs): boolean {
  return current.isAfter(dayjs(), 'day') || current.day() === 0 || current.day() === 6
}

/** 带「是否有分析」圆点标记的日期选择器。 */
export function MarkedDatePicker({ markedDates, ...rest }: MarkedDatePickerProps) {
  const recordedDates = useMemo(() => new Set(markedDates ?? []), [markedDates])
  return (
    <DatePicker
      {...rest}
      disabledDate={rest.disabledDate ?? defaultDisabledDate}
      cellRender={(current, info) => {
        if (info.type !== 'date' || !dayjs.isDayjs(current)) return info.originNode
        const iso = current.format(DATE_FORMAT)
        const hasRecord = recordedDates.has(iso)
        return (
          <div
            className="ant-picker-cell-inner relative"
            title={hasRecord ? `${iso} 已生成分析` : undefined}
          >
            {current.date()}
            {hasRecord && (
              <span className="absolute bottom-[2px] left-1/2 -translate-x-1/2 w-[4px] h-[4px] rounded-full bg-[#5e6ad2]" />
            )}
          </div>
        )
      }}
    />
  )
}
