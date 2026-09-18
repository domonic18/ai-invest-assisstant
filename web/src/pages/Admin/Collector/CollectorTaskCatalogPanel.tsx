/** 执行页左栏任务目录：搜索过滤 + 常用置顶 + 业务分类折叠组（对齐导航菜单），点行开触发弹窗。 */

import { SearchOutlined } from '@ant-design/icons'
import { Empty, Input, Spin } from 'antd'
import { useMemo, useState, type ReactNode } from 'react'

import type { CollectorTaskCatalogItem } from '@ai-invest/shared'

import { getSourceLabel } from '@/utils/collectorTaskLabels'
import {
  TASK_CATEGORY_META,
  taskCategoryOf,
} from '@/utils/taskCategoryMeta'

export const FAV_GROUP_KEY = '__fav__'
const FAV_GROUP_COLOR = '#5e6ad2'

interface CollectorTaskCatalogPanelProps {
  items: CollectorTaskCatalogItem[]
  frequentTasks: string[]
  collapsedGroups: string[]
  onCollapsedGroupsChange: (keys: string[]) => void
  onOpenTask: (item: CollectorTaskCatalogItem) => void
}

function highlight(text: string, keyword: string): ReactNode {
  if (!keyword) return text
  const idx = text.toLowerCase().indexOf(keyword)
  if (idx < 0) return text
  return (
    <>
      {text.slice(0, idx)}
      <mark className="rounded-sm bg-amber-500/30 px-0.5 text-inherit">
        {text.slice(idx, idx + keyword.length)}
      </mark>
      {text.slice(idx + keyword.length)}
    </>
  )
}

function taskMatches(item: CollectorTaskCatalogItem, keyword: string): boolean {
  if (!keyword) return true
  const haystack = [
    item.label,
    item.name,
    ...item.sources,
    ...item.sources.map((s) => getSourceLabel(s)),
  ]
    .join('\n')
    .toLowerCase()
  return haystack.includes(keyword)
}

interface CatalogGroup {
  key: string
  label: string
  color: string
  nav?: string
  items: CollectorTaskCatalogItem[]
}

/** 常用组置顶 + 按业务分类（导航对齐）顺序分组。 */
function buildCatalogGroups(
  items: CollectorTaskCatalogItem[],
  frequentTasks: string[],
): CatalogGroup[] {
  const byName = new Map(items.map((item) => [item.name, item]))
  const groups: CatalogGroup[] = []
  const favItems = frequentTasks
    .map((name) => byName.get(name))
    .filter((item): item is CollectorTaskCatalogItem => item != null)
  if (favItems.length) {
    groups.push({ key: FAV_GROUP_KEY, label: '常用', color: FAV_GROUP_COLOR, items: favItems })
  }
  const byCategory = new Map<string, CollectorTaskCatalogItem[]>()
  for (const item of items) {
    const cat = taskCategoryOf(item.name)
    const arr = byCategory.get(cat)
    if (arr) arr.push(item)
    else byCategory.set(cat, [item])
  }
  for (const [key, meta] of Object.entries(TASK_CATEGORY_META)) {
    const catItems = byCategory.get(key)
    if (!catItems?.length) continue
    groups.push({ key, label: meta.label, color: meta.color, nav: meta.nav, items: catItems })
  }
  return groups
}

function GroupRow({
  item,
  keyword,
  onOpen,
}: {
  item: CollectorTaskCatalogItem
  keyword: string
  onOpen: (item: CollectorTaskCatalogItem) => void
}) {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onOpen(item)}
      onKeyDown={(e) => e.key === 'Enter' && onOpen(item)}
      className="flex cursor-pointer items-center gap-2 rounded-md px-3 py-2 transition-colors hover:bg-white/[0.05]"
    >
      <span className="text-sm text-[#f0f1f5]">{highlight(item.label, keyword)}</span>
      <span className="font-mono text-[11px] text-[#8a8f98]">
        {highlight(item.name, keyword)}
      </span>
      <span className="ml-auto flex shrink-0 gap-1">
        {item.sources.map((s) => (
          <span
            key={s}
            className="rounded border border-white/10 px-1.5 py-0.5 text-[10px] text-[#8a8f98]"
          >
            {getSourceLabel(s)}
          </span>
        ))}
      </span>
    </div>
  )
}

export function CollectorTaskCatalogPanel({
  items,
  frequentTasks,
  collapsedGroups,
  onCollapsedGroupsChange,
  onOpenTask,
}: CollectorTaskCatalogPanelProps) {
  const [search, setSearch] = useState('')
  const keyword = search.trim().toLowerCase()

  const groups = useMemo(() => buildCatalogGroups(items, frequentTasks), [items, frequentTasks])

  const filtered = useMemo(
    () =>
      groups
        .map((g) => ({ ...g, items: g.items.filter((it) => taskMatches(it, keyword)) }))
        .filter((g) => g.items.length > 0),
    [groups, keyword],
  )

  const hitCount = filtered.reduce((sum, g) => sum + g.items.length, 0)

  // 搜索时命中组全部自动展开；无搜索时按折叠偏好（常用组始终展开）
  const expandedKeys = keyword
    ? filtered.map((g) => g.key)
    : filtered
        .map((g) => g.key)
        .filter((key) => key === FAV_GROUP_KEY || !collapsedGroups.includes(key))

  const toggleGroup = (key: string) => {
    if (key === FAV_GROUP_KEY) return
    const next = collapsedGroups.includes(key)
      ? collapsedGroups.filter((k) => k !== key)
      : [...collapsedGroups, key]
    onCollapsedGroupsChange(next)
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-3">
        <Input
          allowClear
          prefix={<SearchOutlined className="text-[#8a8f98]" />}
          placeholder="搜索任务名 / 类型 / 渠道"
          onChange={(e) => setSearch(e.target.value)}
        />
        <span className="shrink-0 text-xs text-[#8a8f98]">
          {keyword ? `${hitCount}/${items.length} 个任务` : `${items.length} 个任务`}
        </span>
      </div>

      {items.length === 0 ? (
        <Spin className="py-8" />
      ) : filtered.length === 0 ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="无匹配任务" />
      ) : (
        <div className="flex flex-col gap-1.5 overflow-y-auto">
          {filtered.map((group) => {
            const expanded = expandedKeys.includes(group.key)
            return (
              <div key={group.key} className="rounded-lg border border-white/10">
                <button
                  type="button"
                  onClick={() => toggleGroup(group.key)}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left"
                >
                  <span
                    className={`text-[10px] text-[#8a8f98] transition-transform ${
                      expanded ? 'rotate-90' : ''
                    }`}
                  >
                    ▶
                  </span>
                  <span
                    className="h-2 w-2 shrink-0 rounded-full"
                    style={{ background: group.color }}
                  />
                  <span
                    className="text-sm font-medium text-[#f0f1f5]"
                    title={group.nav}
                  >
                    {group.label}
                  </span>
                  <span className="rounded-full bg-white/[0.06] px-1.5 text-[11px] text-[#8a8f98]">
                    {group.items.length}
                  </span>
                </button>
                {expanded && (
                  <div className="flex flex-col gap-0.5 px-1.5 pb-1.5">
                    {group.items.map((item) => (
                      <GroupRow key={item.name} item={item} keyword={keyword} onOpen={onOpenTask} />
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
