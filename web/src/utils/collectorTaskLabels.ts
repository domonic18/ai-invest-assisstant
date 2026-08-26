/** 采集渠道的统一中文显示标签。 */
export const SOURCE_LABEL: Record<string, string> = {
  sina: '新浪财经',
  eastmoney: '东方财富',
  ths: '同花顺',
  cninfo: '巨潮资讯',
  exchange: '沪深交易所',
  tushare: 'Tushare Pro',
  internal: '内部生成',
}

/** 获取渠道标识的中文显示名；未配置时返回原始 source。 */
export function getSourceLabel(source: string | null | undefined): string {
  if (!source) return '-'
  return SOURCE_LABEL[source] ?? source
}

/** 采集任务/数据类型的统一中文显示标签。 */
export const COLLECTOR_TASK_LABEL: Record<string, string> = {
  kline: 'K 线',
  'index-kline': '指数 K 线',
  'etf-kline': 'ETF 日 K',
  'a50-kline': '富时 A50 日 K',
  auction: '集合竞价',
  'fund-flow': '资金流向',
  news: '新闻',
  'company-profile': '公司概况',
  disclosure: '公告披露',
  'sector-fund-flow': '板块资金流向',
  'dragon-list': '龙虎榜',
  'research-report': '个股研报',
  'concept-constituents': '概念成分股',
  'financial-report': '财报',
  'ipo-info': 'IPO 信息',
  'fund-holdings': '基金持仓',
  macro: '宏观经济',
  quote: '行情快照',
  'stock-list': '股票列表',
  'limit-up-pool': '涨停股池',
  'market-breadth': '涨跌统计',
  'index-spot': '指数快照',
  'index-minute': '指数分钟线',
  'index-auction': '指数集合竞价',
  'stock-minute': '个股分钟线',
  'market-amount': '市场成交额',
  'broken-pool': '炸板统计',
  'limit-down-pool': '跌停股池',
  'market-daily-review': '每日市场复盘',
}

/** 获取任务/数据类型的中文显示名；未配置时返回原始 key。 */
export function getTaskLabel(taskName: string | null | undefined): string {
  if (!taskName) return '-'
  return COLLECTOR_TASK_LABEL[taskName] ?? taskName
}
