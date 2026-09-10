import { Empty, Spin } from 'antd'
import { useEffect, useMemo, useState } from 'react'
import type { WatchlistGroup } from '@ai-invest/shared'

import { useWatchlistQuotes } from '@/hooks/useMarket'
import { useWatchlistGroups } from '@/hooks/useWatchlistGroups'
import { StockDetailContent } from '@/pages/StockDetail/StockDetailContent'

import { GroupFormModal } from './components/GroupFormModal'
import { GroupTabBar } from './components/GroupTabBar'
import { ScreenshotImportModal } from './components/ScreenshotImportModal'
import { WatchlistStockList } from './components/WatchlistStockList'

export function Watchlist() {
  const { data: groups, isLoading } = useWatchlistGroups()
  const { data: quotes } = useWatchlistQuotes()
  const [activeGroupId, setActiveGroupId] = useState<number | null>(null)
  const [selectedCode, setSelectedCode] = useState<string | null>(null)
  const [formOpen, setFormOpen] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const [editing, setEditing] = useState<WatchlistGroup | null>(null)

  const quotesByCode = useMemo(
    () => new Map((quotes ?? []).map((quote) => [quote.code, quote])),
    [quotes],
  )

  const visibleCodes = useMemo(() => {
    const source =
      activeGroupId === null
        ? (groups ?? []).flatMap((g) => g.items)
        : (groups ?? []).find((g) => g.id === activeGroupId)?.items ?? []
    return source.map((item) => item.code)
  }, [groups, activeGroupId])

  // 分组切换或列表变化后，选中项缺失时回退到当前组第一只
  useEffect(() => {
    if (visibleCodes.length === 0) {
      setSelectedCode(null)
      return
    }
    if (!selectedCode || !visibleCodes.includes(selectedCode)) {
      setSelectedCode(visibleCodes[0])
    }
  }, [visibleCodes, selectedCode])

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <Spin />
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      <GroupTabBar
        groups={groups ?? []}
        activeGroupId={activeGroupId}
        onChange={setActiveGroupId}
        onNewGroup={() => {
          setEditing(null)
          setFormOpen(true)
        }}
        onEditGroup={(group) => {
          setEditing(group)
          setFormOpen(true)
        }}
        onImport={() => setImportOpen(true)}
      />

      <div className="flex-1 flex min-h-0 flex-col lg:flex-row">
        <div className="w-full lg:w-[300px] shrink-0 max-h-64 lg:max-h-none border-b lg:border-b-0 lg:border-r border-gray-800 flex flex-col">
          <WatchlistStockList
            groups={groups ?? []}
            activeGroupId={activeGroupId}
            quotesByCode={quotesByCode}
            selectedCode={selectedCode}
            onSelect={setSelectedCode}
          />
        </div>
        <div className="flex-1 min-w-0 min-h-0">
          {selectedCode ? (
            <StockDetailContent stockCode={selectedCode} />
          ) : (
            <div className="h-full flex items-center justify-center">
              <Empty description="暂无自选股，可通过顶部搜索或截图导入添加" />
            </div>
          )}
        </div>
      </div>

      <GroupFormModal open={formOpen} group={editing} onClose={() => setFormOpen(false)} />
      <ScreenshotImportModal
        open={importOpen}
        groups={groups ?? []}
        onClose={() => setImportOpen(false)}
      />
    </div>
  )
}
