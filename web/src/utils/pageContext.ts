/** 从当前路由构建助手 page_context（后端注入用户消息前缀，解析"这只股票"等指代）。
 *
 * 真相源约定（URL as source of truth）：标的一律由 URL 承载——路径参数页
 * （/stock/:code 等）取路径段，无参数页（自选页）取 ?code= 查询参数；
 * 本函数是纯函数，入参兼容 window.location，调用方零订阅（发送瞬间读取）。
 */

export interface PageContextLocation {
  pathname: string
  search?: string
}

export interface PageContext {
  route: string
  page?: string
  stock_code?: string
  industry?: string
  sector_type?: string
  sector_code?: string
  index_code?: string
}

export function buildPageContext(location: PageContextLocation | string): PageContext {
  const { pathname: route, search } =
    typeof location === 'string' ? { pathname: location, search: undefined } : location
  const context: PageContext = { route }

  const stock = route.match(/^\/stock\/(\d{6})/)
  if (stock) {
    context.page = '个股详情'
    context.stock_code = stock[1]
    return context
  }
  const financial = route.match(/^\/financial\/(\d{6})/)
  if (financial) {
    context.page = '财务分析'
    context.stock_code = financial[1]
    return context
  }
  const sector = route.match(/^\/sector\/([a-z]+)\/([^/?#]+)/)
  if (sector) {
    context.page = '板块详情'
    context.sector_type = sector[1]
    context.sector_code = sector[2]
    return context
  }
  const index = route.match(/^\/index\/([^/?#]+)/)
  if (index) {
    context.page = '指数详情'
    context.index_code = index[1]
    return context
  }
  const chain = route.match(/^\/chain\/([^/?#]+)/)
  if (chain) {
    context.page = '产业链分析'
    context.industry = decodeURIComponent(chain[1])
    return context
  }
  if (route.startsWith('/workbench')) context.page = '工作台'
  else if (route.startsWith('/review')) context.page = '每日复盘'
  else if (route.startsWith('/capital-flow')) context.page = '资金流向'
  else if (route.startsWith('/auction')) context.page = '集合竞价'
  else if (route.startsWith('/hotspot')) context.page = '热点追踪'
  else if (route.startsWith('/research')) context.page = '研报中心'
  else if (route.startsWith('/watchlist')) {
    // 自选页选中标的由 URL ?code= 承载（页面 setSearchParams 维护）
    context.page = '自选股'
    const code = new URLSearchParams(search ?? '').get('code')
    if (code && /^\d{6}$/.test(code)) context.stock_code = code
  }
  return context
}
