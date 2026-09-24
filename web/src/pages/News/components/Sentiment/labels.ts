/** 大 V 情绪 Tab 展示标签：与后端 SocialCategory / SocialTargetType / SentimentStance 枚举对齐。 */

import type { ApiSocialStance, ApiSocialTargetType } from '@ai-invest/shared'

export const STANCE_TEXT: Record<ApiSocialStance, string> = {
  bullish: '看多',
  bearish: '看空',
  neutral: '中性',
}

export const CATEGORY_LABELS: Record<string, string> = {
  macro_policy: '宏观政策',
  finance_kol: '财经KOL',
  industry: '行业',
}

export const TARGET_TYPE_LABELS: Record<ApiSocialTargetType, string> = {
  index: '指数',
  sector: '板块',
  stock: '个股',
  commodity: '商品',
}
