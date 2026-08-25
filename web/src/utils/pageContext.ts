/** 从当前路由构建助手 page_context（后端注入用户消息前缀，解析"这只股票"等指代） */

export interface PageContext {
  route: string
  page?: string
  stock_code?: string
  industry?: string
}

export function buildPageContext(pathname: string): PageContext {
  const context: PageContext = { route: pathname }

  const stock = pathname.match(/^\/stock\/(\d{6})/)
  if (stock) {
    context.page = '个股详情'
    context.stock_code = stock[1]
    return context
  }
  const financial = pathname.match(/^\/financial\/(\d{6})/)
  if (financial) {
    context.page = '财务分析'
    context.stock_code = financial[1]
    return context
  }
  const chain = pathname.match(/^\/chain\/([^/?#]+)/)
  if (chain) {
    context.page = '产业链分析'
    context.industry = decodeURIComponent(chain[1])
    return context
  }
  if (pathname.startsWith('/capital-flow')) context.page = '资金流向'
  else if (pathname.startsWith('/auction')) context.page = '集合竞价'
  else if (pathname.startsWith('/hotspot')) context.page = '热点追踪'
  else if (pathname.startsWith('/research')) context.page = '研报中心'
  return context
}
