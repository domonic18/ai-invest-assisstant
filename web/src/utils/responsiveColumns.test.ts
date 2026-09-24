import { describe, expect, it } from 'vitest'

import { narrowColumns } from './responsiveColumns'

interface Row {
  name: string
  pct: number
  note: string
}

const columns = [
  { title: '个股', key: 'name', dataIndex: 'name', width: 170, fixed: 'left' as const },
  { title: '涨跌幅', key: 'pct', dataIndex: 'pct', width: 90 },
  { title: '备注', dataIndex: 'note' },
  { title: '操作', key: 'action', width: 90, fixed: 'right' as const },
]

describe('narrowColumns', () => {
  it('keeps only whitelisted columns in original order (key or dataIndex)', () => {
    const result = narrowColumns<Row>(columns, ['name', 'note', 'action'])
    expect(result.map((c) => c.title)).toEqual(['个股', '备注', '操作'])
  })

  it('strips fixed anchors from all kept columns', () => {
    const result = narrowColumns<Row>(columns, ['name', 'action'])
    expect(result.every((c) => c.fixed === undefined)).toBe(true)
  })
})
