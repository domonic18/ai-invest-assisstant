/** 任务业务分类：目录分组与日历着色的单一真相源。
 * catalog 的 dataType 字段是任务名模板（如 kline_{period}）无分组语义，
 * 故按任务 name 建业务级映射，分类措辞对齐系统导航菜单（监测/资讯/分析/后台）。 */

export interface TaskCategoryMeta {
  label: string
  color: string
  /** 对应的系统导航菜单位置（组头 tooltip）。 */
  nav?: string
}

/** 分类定义按展示顺序排列（常用组外置顶）。 */
export const TASK_CATEGORY_META: Record<string, TaskCategoryMeta> = {
  monitor: { label: '行情监测', color: '#58a6ff', nav: '导航：监测（K 线 / 行情 / 自选）' },
  macro: { label: '宏观全球', color: '#f2cc60', nav: '导航：监测 → 宏观指数' },
  auction: { label: '集合竞价', color: '#2ea043', nav: '导航：监测 → 集合竞价' },
  sector: { label: '板块资金', color: '#22d3ee', nav: '导航：监测 → 板块监测' },
  pool: { label: '热点股池', color: '#f85149', nav: '工作台 · 涨停/龙虎榜股池' },
  news: { label: '资讯电报', color: '#fb923c', nav: '导航：资讯 → 资讯中心 / 投资日历' },
  fundamental: { label: '个股资料', color: '#ce9178', nav: '个股页 · 基本面资料' },
  ai: { label: 'AI 自动化', color: '#a78bfa', nav: '定时 AI 自动化（复盘 / 异动 / 资讯分级 / 情绪）' },
  social: { label: '社媒采集', color: '#f472b6', nav: '导航：后台 → 社媒追踪' },
  maintenance: { label: '系统维护', color: '#8a8f98' },
  other: { label: '其他', color: '#5c616e' },
}

/** 任务 name（= AdminTask.taskType / catalog item.name）→ 业务分类。 */
const TASK_CATEGORY_OF: Record<string, string> = {
  // 行情监测：K 线 / 快照 / 分钟线 / 大盘统计
  kline: 'monitor',
  'watchlist-kline-daily': 'monitor',
  'index-kline': 'monitor',
  'etf-kline': 'monitor',
  'a50-kline': 'monitor',
  'sector-kline': 'monitor',
  'kline-freshness': 'monitor',
  quote: 'monitor',
  'index-spot': 'monitor',
  'index-minute': 'monitor',
  'stock-minute': 'monitor',
  'market-breadth': 'monitor',
  'market-amount': 'monitor',
  // 宏观全球
  'global-index': 'macro',
  'fed-watch': 'macro',
  macro: 'macro',
  // 集合竞价
  auction: 'auction',
  'index-auction': 'auction',
  // 板块资金
  'sector-quote': 'sector',
  'fund-flow': 'sector',
  'sector-fund-flow': 'sector',
  // 热点股池
  'limit-up-pool': 'pool',
  'limit-down-pool': 'pool',
  'broken-pool': 'pool',
  'dragon-list': 'pool',
  // 资讯电报
  news: 'news',
  'news-subscription-match': 'news',
  'cls-telegraph-backfill': 'news',
  'cls-investkalendar': 'news',
  // 个股资料
  'stock-list': 'fundamental',
  'stock-shares': 'fundamental',
  'financial-statement': 'fundamental',
  'concept-constituents': 'fundamental',
  'company-profile': 'fundamental',
  disclosure: 'fundamental',
  'financial-report': 'fundamental',
  'ipo-info': 'fundamental',
  'fund-holdings': 'fundamental',
  'research-report': 'fundamental',
  // AI 自动化（internal 定时任务，单独列举）
  'market-daily-review': 'ai',
  'limit-up-ai-review': 'ai',
  'stock-daily-analysis': 'ai',
  'chain-refresh': 'ai',
  'news-score': 'ai',
  'news-storyline': 'ai',
  'news-topic': 'ai',
  'sector-anomaly': 'ai',
  'stock-anomaly': 'ai',
  'social-sentiment': 'ai',
  // 社媒采集
  'social-video': 'social',
  // 系统维护
  'collector-log-cleanup': 'maintenance',
  'health-check': 'maintenance',
}

export function taskCategoryOf(taskName: string): string {
  return TASK_CATEGORY_OF[taskName] ?? 'other'
}

export function taskCategoryLabel(category: string): string {
  return TASK_CATEGORY_META[category]?.label ?? category
}

export function taskCategoryColor(category: string): string {
  return TASK_CATEGORY_META[category]?.color ?? '#5c616e'
}
