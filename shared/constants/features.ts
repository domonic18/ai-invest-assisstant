/**
 * 功能模块目录：与后端 app/constants/features.py 保持一致。
 * 不在目录内的路由（工作台/行情/个股等核心浏览）对所有用户开放。
 */

export const FEATURE_KEYS = [
  'kb',
  'assistant',
  'screening',
  'research',
  'financial-reports',
  'paper-trade',
  'skills',
  'news',
  'chain',
  'anomaly',
  'auction',
  'fund-flow',
] as const

export type FeatureKey = (typeof FEATURE_KEYS)[number]

export interface FeatureCatalogItem {
  key: FeatureKey
  label: string
  category: string
}

export const FEATURE_CATALOG: FeatureCatalogItem[] = [
  { key: 'kb', label: '知识库查询', category: 'AI 能力' },
  { key: 'assistant', label: 'AI 助手', category: 'AI 能力' },
  { key: 'screening', label: 'AI 选股', category: 'AI 能力' },
  { key: 'research', label: 'AI 研报', category: 'AI 能力' },
  { key: 'financial-reports', label: 'AI 财报解读', category: 'AI 能力' },
  { key: 'paper-trade', label: '模拟交易', category: '交易与工具' },
  { key: 'skills', label: '技能广场', category: '交易与工具' },
  { key: 'news', label: '资讯中心', category: '行情与数据' },
  { key: 'chain', label: '产业图谱', category: '行情与数据' },
  { key: 'anomaly', label: '异动监测', category: '行情与数据' },
  { key: 'auction', label: '集合竞价', category: '行情与数据' },
  { key: 'fund-flow', label: '资金流向', category: '行情与数据' },
]

/** 按分类分组（供组编辑表单 Checkbox 分组渲染）。 */
export const FEATURE_CATEGORIES: { category: string; items: FeatureCatalogItem[] }[] =
  FEATURE_CATALOG.reduce(
    (acc, item) => {
      const bucket = acc.find((b) => b.category === item.category)
      if (bucket) {
        bucket.items.push(item)
      } else {
        acc.push({ category: item.category, items: [item] })
      }
      return acc
    },
    [] as { category: string; items: FeatureCatalogItem[] }[]
  )

export const FEATURE_LABELS: Record<FeatureKey, string> = FEATURE_CATALOG.reduce(
  (acc, item) => {
    acc[item.key] = item.label
    return acc
  },
  {} as Record<FeatureKey, string>
)

/** 判断用户是否可用某功能模块：admin 不受限，否则查其权限集。 */
export function canAccessFeature(
  user: { isAdmin: boolean; permissions?: string[] } | null,
  feature: FeatureKey
): boolean {
  if (!user) return false
  if (user.isAdmin) return true
  return (user.permissions ?? []).includes(feature)
}
