import { describe, expect, it } from 'vitest'

import { buildPageContext } from './pageContext'

describe('buildPageContext', () => {
  it('解析个股详情页股票代码', () => {
    expect(buildPageContext('/stock/000001')).toEqual({
      route: '/stock/000001',
      page: '个股详情',
      stock_code: '000001',
    })
  })

  it('解析财务分析页', () => {
    const context = buildPageContext('/financial/600519')
    expect(context.page).toBe('财务分析')
    expect(context.stock_code).toBe('600519')
  })

  it('解析产业链页行业名（含中文编码）', () => {
    const context = buildPageContext(`/chain/${encodeURIComponent('半导体')}`)
    expect(context.page).toBe('产业链分析')
    expect(context.industry).toBe('半导体')
  })

  it('解析板块详情页类型与代码（画线 target 同源）', () => {
    expect(buildPageContext('/sector/industry/881125')).toEqual({
      route: '/sector/industry/881125',
      page: '板块详情',
      sector_type: 'industry',
      sector_code: '881125',
    })
    expect(buildPageContext('/sector/concept/new_ssjj').sector_code).toBe('new_ssjj')
  })

  it('解析指数详情页指数代码', () => {
    expect(buildPageContext('/index/sh000001')).toEqual({
      route: '/index/sh000001',
      page: '指数详情',
      index_code: 'sh000001',
    })
  })

  it('板块异动页不误判为板块详情', () => {
    expect(buildPageContext('/anomaly/sector')).not.toHaveProperty('sector_code')
  })

  it('识别工作台与每日复盘页', () => {
    expect(buildPageContext('/workbench').page).toBe('工作台')
    expect(buildPageContext('/review').page).toBe('每日复盘')
  })

  it('识别无参数的普通页面', () => {
    expect(buildPageContext('/capital-flow').page).toBe('资金流向')
    expect(buildPageContext('/').page).toBeUndefined()
  })
})
