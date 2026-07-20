import type { CollectorTaskName } from '@ai-invest/shared'

export const SOURCE_LABEL: Record<string, string> = {
  sina: '新浪财经',
  eastmoney: '东方财富',
  ths: '同花顺',
  cninfo: '巨潮资讯',
  exchange: '沪深交易所',
}

export const DATA_TYPE_LABEL: Record<CollectorTaskName, string> = {
  kline: 'K 线',
  'index-kline': '指数 K 线',
  auction: '集合竞价',
  'fund-flow': '资金流向',
  news: '新闻',
  'company-profile': '公司概况',
  disclosure: '公告披露',
  'sector-fund-flow': '板块资金流向',
  'dragon-list': '龙虎榜',
  'research-report': '个股研报',
  'financial-report': '财报',
  'ipo-info': 'IPO 信息',
  'fund-holdings': '基金持仓',
  macro: '宏观经济',
  'stock-list': '股票列表',
  'limit-up-pool': '涨停股池',
  'market-breadth': '涨跌统计',
  'index-spot': '指数快照',
  'index-minute': '指数分钟线',
  'market-amount': '市场成交额',
  'broken-pool': '炸板统计',
}
