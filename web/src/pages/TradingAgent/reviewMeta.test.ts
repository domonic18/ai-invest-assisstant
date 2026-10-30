/** reviewMeta 纯函数测试：六档标签、>12 月区间判定（与后端映射口径一致）、窗口文案。 */
import dayjs from 'dayjs'
import { describe, expect, it } from 'vitest'

import {
  CUSTOM_RANGE_TOO_LONG,
  describeWindow,
  isRangeTooLong,
  REVIEW_PERIOD_OPTIONS,
} from './reviewMeta'

describe('reviewMeta', () => {
  it('六个周期按日/周/月/季/半年/年排列', () => {
    expect(REVIEW_PERIOD_OPTIONS.map((option) => option.value)).toEqual([
      'day',
      'week',
      'month',
      'quarter',
      'half_year',
      'year',
    ])
    expect(REVIEW_PERIOD_OPTIONS.map((option) => option.label).join('')).toBe('日周月季半年年')
  })

  it('超过 12 个月的区间提示改用年档', () => {
    const start = dayjs('2025-10-29')
    expect(isRangeTooLong(start, start.add(12, 'month'))).toBe(false)
    expect(isRangeTooLong(start, start.add(12, 'month').add(1, 'day'))).toBe(true)
    expect(CUSTOM_RANGE_TOO_LONG).toContain('年档')
  })

  it('窗口文案区分区间/本期/上期', () => {
    expect(describeWindow({ startDate: '2026-06-01', endDate: '2026-07-17' })).toBe(
      '2026-06-01 ~ 2026-07-17',
    )
    expect(describeWindow({ period: 'month', scope: 'current' })).toBe('月本期')
    expect(describeWindow({ period: 'quarter', scope: 'previous', tradeDate: '2026-07-17' })).toBe(
      '季上期（基准日 2026-07-17）',
    )
  })
})
