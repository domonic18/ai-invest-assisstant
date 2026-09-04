import type { CalendarEventCategory } from '@ai-invest/shared'

export interface CategoryMeta {
  /** AntD Tag color 名。 */
  tagColor: string
  /** 月/周视图事件 chip 的左侧色条 + 底色 + 文字色。 */
  chipClass: string
  /** 日级事件 · 占位的文字色（列表等无 chip 底色的场景）。 */
  dotClass: string
}

export const CATEGORY_META: Record<CalendarEventCategory, CategoryMeta> = {
  宏观: {
    tagColor: 'blue',
    chipClass: 'border-l-blue-500 bg-blue-500/10 text-blue-400',
    dotClass: 'text-blue-400',
  },
  央行动态: {
    tagColor: 'geekblue',
    chipClass: 'border-l-indigo-500 bg-indigo-500/10 text-indigo-300',
    dotClass: 'text-indigo-300',
  },
  新股: {
    tagColor: 'green',
    chipClass: 'border-l-green-500 bg-green-500/10 text-green-400',
    dotClass: 'text-green-400',
  },
  解禁: {
    tagColor: 'gold',
    chipClass: 'border-l-amber-500 bg-amber-500/10 text-amber-400',
    dotClass: 'text-amber-400',
  },
  财报: {
    tagColor: 'red',
    chipClass: 'border-l-red-500 bg-red-500/10 text-red-400',
    dotClass: 'text-red-400',
  },
  会议: {
    tagColor: 'default',
    chipClass: 'border-l-gray-500 bg-gray-500/10 text-gray-400',
    dotClass: 'text-gray-400',
  },
}

export function categoryMeta(category: CalendarEventCategory): CategoryMeta {
  return CATEGORY_META[category] ?? CATEGORY_META['会议']
}
