import { CaretDownOutlined, CaretUpOutlined, EllipsisOutlined, MinusCircleOutlined } from '@ant-design/icons'
import { Button, Dropdown, Empty, Popconfirm, message } from 'antd'
import type { MenuProps } from 'antd'
import { useMemo, useRef, useState } from 'react'
import type { KeyboardEvent as ReactKeyboardEvent } from 'react'
import type { WatchlistGroup, WatchlistItem, WatchlistQuote } from '@ai-invest/shared'

import { IntradaySpark } from '@/components/charts/IntradaySpark'
import { isKlineHovered } from '@/components/charts/useKlineKeyboardNav'
import { useMoveWatchlistItem } from '@/hooks/useWatchlistGroups'
import { useRemoveWatchlistItem } from '@/hooks/useWatchlist'
import { useColorScheme } from '@/stores/settings'
import { apiErrorMessage } from '@/utils/errorMessage'
import { changeColor, formatPercent } from '@/utils/formatters'

type SortField = 'changePct' | 'price' | 'amount' | 'name'
type SortOrder = 'asc' | 'desc'

interface SortState {
  field: SortField
  order: SortOrder
}

const SORT_FIELD_LABELS: Record<SortField, string> = {
  changePct: '涨幅',
  price: '现价',
  amount: '成交额',
  name: '名称',
}

function sortValue(
  item: WatchlistItem,
  quote: WatchlistQuote | undefined,
  field: SortField,
): string | number | null {
  switch (field) {
    case 'name':
      return quote?.name ?? item.name ?? item.code
    case 'price':
      return quote?.price ?? null
    case 'amount':
      return quote?.amount ?? null
    default:
      return quote?.changePct ?? null
  }
}

interface WatchlistStockListProps {
  groups: WatchlistGroup[]
  /** null 表示「全部」分组。 */
  activeGroupId: number | null
  quotesByCode: Map<string, WatchlistQuote>
  selectedCode: string | null
  onSelect: (code: string) => void
}

/** 同花顺式自选列表：名称 / 分时缩略图 / 涨幅·现价，表头点击排序。 */
export function WatchlistStockList({
  groups,
  activeGroupId,
  quotesByCode,
  selectedCode,
  onSelect,
}: WatchlistStockListProps) {
  useColorScheme()
  const moveItem = useMoveWatchlistItem()
  const removeItem = useRemoveWatchlistItem()
  const [sort, setSort] = useState<SortState | null>(null)
  // 删除/移动入口只在编辑管理模式出现，避免浏览时误触
  const [managing, setManaging] = useState(false)
  const listRef = useRef<HTMLDivElement | null>(null)

  const items = useMemo(() => {
    const source =
      activeGroupId === null
        ? groups.flatMap((g) => g.items)
        : (groups.find((g) => g.id === activeGroupId)?.items ?? [])
    if (!sort) return source
    const sorted = [...source].sort((a, b) => {
      const va = sortValue(a, quotesByCode.get(a.code), sort.field)
      const vb = sortValue(b, quotesByCode.get(b.code), sort.field)
      if (va === null && vb === null) return 0
      if (va === null) return 1
      if (vb === null) return -1
      const cmp =
        typeof va === 'string' || typeof vb === 'string'
          ? String(va).localeCompare(String(vb), 'zh-Hans-CN')
          : Number(va) - Number(vb)
      return sort.order === 'asc' ? cmp : -cmp
    })
    return sorted
  }, [groups, activeGroupId, quotesByCode, sort])

  const orderedCodes = useMemo(() => items.map((item) => item.code), [items])

  // 列表聚焦时 ↑/↓ 切换个股；鼠标悬浮 K 线图时让位图表缩放（web 无 canvas 焦点，悬浮即"图表焦点"）
  const handleListKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    if (managing) return
    if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return
    if (isKlineHovered()) return
    event.preventDefault()
    if (!orderedCodes.length) return
    const current = selectedCode ? orderedCodes.indexOf(selectedCode) : -1
    const next =
      event.key === 'ArrowDown'
        ? current < 0
          ? 0
          : Math.min(orderedCodes.length - 1, current + 1)
        : current < 0
          ? orderedCodes.length - 1
          : Math.max(0, current - 1)
    if (next === current) return
    const code = orderedCodes[next]
    onSelect(code)
    requestAnimationFrame(() => {
      listRef.current
        ?.querySelector(`[data-code="${CSS.escape(code)}"]`)
        ?.scrollIntoView({ block: 'nearest' })
    })
  }

  const toggleSort = (field: SortField) => {
    setSort((prev) => {
      if (!prev || prev.field !== field) return { field, order: 'desc' }
      if (prev.order === 'desc') return { field, order: 'asc' }
      return null
    })
  }

  const sortIndicator = (field: SortField) => {
    if (!sort || sort.field !== field) {
      return <CaretUpOutlined className="text-[10px] text-gray-600" />
    }
    return sort.order === 'desc' ? (
      <CaretDownOutlined className="text-[10px] text-blue-400" />
    ) : (
      <CaretUpOutlined className="text-[10px] text-blue-400" />
    )
  }

  const fieldMenu: MenuProps = {
    items: (['changePct', 'price', 'amount'] as SortField[]).map((field) => ({
      key: field,
      label: SORT_FIELD_LABELS[field],
    })),
    selectedKeys: sort ? [sort.field] : [],
    onClick: ({ key }) => toggleSort(key as SortField),
  }

  const moveMenu = (item: WatchlistItem): MenuProps => ({
    items: groups
      .filter((g) => g.id !== item.groupId)
      .map((g) => ({ key: String(g.id), label: g.name })),
    onClick: ({ key, domEvent }) => {
      domEvent.stopPropagation()
      moveItem.mutate(
        { itemId: item.id, groupId: Number(key) },
        {
          onSuccess: () => message.success('已移动'),
          onError: (err) => message.error(apiErrorMessage(err, '移动失败')),
        },
      )
    },
  })

  const quoteFieldLabel =
    sort && sort.field !== 'name' ? SORT_FIELD_LABELS[sort.field] : SORT_FIELD_LABELS.changePct

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center px-3 py-1.5 border-b border-gray-800 text-xs text-gray-500 shrink-0">
        <button
          type="button"
          className="flex items-center gap-0.5 hover:text-gray-300"
          onClick={() => toggleSort('name')}
        >
          名称{sortIndicator('name')}
        </button>
        <span className="flex-1 text-center">分时</span>
        <Dropdown menu={fieldMenu} placement="bottomRight">
          <button
            type="button"
            className="flex items-center gap-0.5 hover:text-gray-300"
            onClick={(e) => {
              e.stopPropagation()
              toggleSort(sort?.field !== 'name' && sort ? sort.field : 'changePct')
            }}
          >
            {quoteFieldLabel}
            {sortIndicator(sort?.field !== 'name' && sort ? sort.field : 'changePct')}
          </button>
        </Dropdown>
        <span className="ml-2 pl-2 border-l border-gray-800">
          <button
            type="button"
            className={`text-xs ${managing ? 'text-blue-400' : 'hover:text-gray-300'}`}
            onClick={() => setManaging((v) => !v)}
          >
            {managing ? '完成' : '管理'}
          </button>
        </span>
      </div>

      <div
        ref={listRef}
        role="listbox"
        aria-label="自选股列表"
        tabIndex={0}
        onKeyDown={handleListKeyDown}
        className="flex-1 overflow-y-auto focus-visible:outline focus-visible:outline-1 focus-visible:outline-[#5e6ad2]"
      >
        {items.length === 0 ? (
          <Empty
            className="mt-10"
            description="暂无自选股，可通过顶部搜索或截图导入添加"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        ) : (
          items.map((item) => {
            const quote = quotesByCode.get(item.code)
            const selected = !managing && item.code === selectedCode
            return (
              <div
                key={item.id}
                role="option"
                aria-selected={selected}
                data-code={item.code}
                onClick={() => {
                  if (!managing) onSelect(item.code)
                }}
                className={`flex items-center gap-2 px-3 py-2 border-b border-gray-800/60 ${
                  managing
                    ? 'cursor-default'
                    : `cursor-pointer ${selected ? 'bg-[#1c1f26]' : 'hover:bg-[#15181e]'}`
                }`}
              >
                {managing && (
                  <span className="shrink-0 flex items-center" onClick={(e) => e.stopPropagation()}>
                    <Popconfirm
                      title="删除自选股"
                      description={`确定删除 ${item.code} 吗？`}
                      okText="删除"
                      cancelText="取消"
                      onConfirm={() =>
                        removeItem.mutate(item.id, {
                          onSuccess: () => message.success('已删除'),
                          onError: (err) => message.error(apiErrorMessage(err, '删除失败')),
                        })
                      }
                    >
                      <Button
                        type="text"
                        size="small"
                        danger
                        icon={<MinusCircleOutlined />}
                        aria-label={`删除 ${quote?.name ?? item.code}`}
                      />
                    </Popconfirm>
                  </span>
                )}
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm text-gray-200">
                    {quote?.name ?? item.name ?? item.code}
                  </div>
                  <div className="text-xs text-gray-500 font-mono">{item.code}</div>
                </div>
                <IntradaySpark points={quote?.trend} changePct={quote?.changePct ?? null} width={64} />
                <div className="text-right shrink-0 w-[72px]">
                  <div className="font-mono text-sm text-gray-200">
                    {quote?.price != null ? quote.price.toFixed(2) : '-'}
                  </div>
                  <div className={`text-xs font-mono ${changeColor(quote?.changePct)}`}>
                    {quote?.changePct != null ? formatPercent(quote.changePct) : '-'}
                  </div>
                </div>
                {managing && groups.length > 1 && (
                  <span className="shrink-0 flex items-center" onClick={(e) => e.stopPropagation()}>
                    <Dropdown menu={moveMenu(item)} placement="bottomRight" trigger={['click']}>
                      <Button type="text" size="small" icon={<EllipsisOutlined />} />
                    </Dropdown>
                  </span>
                )}
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
