export {
  COLLECTOR_TASK_LABEL as DATA_TYPE_LABEL,
  SOURCE_LABEL,
  getSourceLabel,
  getTaskLabel,
} from '@/utils/collectorTaskLabels'

/** 数据类型在树形选择器中的分组归属与展示顺序；未命中的任务归入「其他」。 */
export const DATA_TYPE_GROUPS: Array<{ label: string; types: string[] }> = [
  {
    label: '行情 K 线 / 分钟线',
    types: [
      'kline_{period}',
      'etf_kline',
      'a50_kline',
      'sector_kline',
      'index_kline',
      'stock_minute',
      'index_minute',
      'watchlist_kline_daily',
      'kline_freshness',
    ],
  },
  {
    label: '快照与集合竞价',
    types: ['quote', 'index_spot', 'sector_quote', 'auction', 'quote_auction_index'],
  },
  {
    label: '资金与市场统计',
    types: [
      'fund_flow',
      'capital_fund_flow_sector',
      'market_amount',
      'market_breadth',
      'pool_limit_up_stock',
      'limit_down_pool',
      'broken_pool',
      'pool_dragon_tiger_stock',
    ],
  },
  {
    label: '资讯与研报',
    types: [
      'news',
      'news_telegraph',
      'news_subscription_hit',
      'disclosure',
      'research_report',
      'invest_calendar',
    ],
  },
  {
    label: '基本面与参考数据',
    types: [
      'company_profile',
      'financial_statement',
      'financial_statement_em',
      'stock_shares',
      'stock_list',
      'fund_holding',
      'ipo_info',
      'mapping_stock_concept',
    ],
  },
  {
    label: '宏观与全球',
    types: ['macro_indicator', 'global_index', 'fed_watch'],
  },
  {
    label: 'AI 内部生成',
    types: [
      'ai_chain_refresh',
      'ai_limit_up_review',
      'ai_market_daily_review',
      'ai_news_score',
      'ai_news_storyline',
      'ai_news_topic',
      'ai_sector_anomaly',
      'ai_stock_anomaly',
      'ai_stock_daily_analysis',
    ],
  },
  {
    label: '系统维护',
    types: ['system_maintenance'],
  },
]
