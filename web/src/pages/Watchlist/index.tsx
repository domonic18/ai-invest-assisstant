import { ArrowLeftOutlined } from '@ant-design/icons'
import { Button, Empty, Spin } from 'antd'
import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import type { WatchlistGroup } from '@ai-invest/shared'

import { useWatchlistQuotes } from '@/hooks/useMarket'
import { useWatchlistGroups } from '@/hooks/useWatchlistGroups'
import { useIsNarrowScreen } from '@/hooks/useIsNarrowScreen'
import { StockDetailContent } from '@/pages/StockDetail/StockDetailContent'

import { GroupFormModal } from './components/GroupFormModal'
import { GroupTabBar } from './components/GroupTabBar'
import { ScreenshotImportModal } from './components/ScreenshotImportModal'
import { WatchlistStockList } from './components/WatchlistStockList'

export function Watchlist() {
  const { data: groups, isLoading } = useWatchlistGroups()
  const { data: quotes } = useWatchlistQuotes()
  const isNarrow = useIsNarrowScreen()
  const [activeGroupId, setActiveGroupId] = useState<number | null>(null)
  const [formOpen, setFormOpen] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const [editing, setEditing] = useState<WatchlistGroup | null>(null)

  // 选中标的由 URL ?code= 承载（真相源单一化）：刷新/分享保持选中，
  // 助手 page_context 纯函数解析，无需任何额外全局通道
  const [searchParams, setSearchParams] = useSearchParams()
  const selectedCode = searchParams.get('code')
  const selectCode = (code: string) => setSearchParams({ code }, { replace: true })

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

  // 分组切换或列表变化后，选中项缺失时回退到当前组第一只（仍写回 URL）。
  // 窄屏单栏交互不自动选中（详情会整屏替换列表），仅清掉已失效的选中项
  useEffect(() => {
    if (visibleCodes.length === 0) {
      if (selectedCode) setSearchParams({}, { replace: true })
      return
    }
    if (isNarrow) {
      if (selectedCode && !visibleCodes.includes(selectedCode)) {
        setSearchParams({}, { replace: true })
      }
      return
    }
    if (!selectedCode || !visibleCodes.includes(selectedCode)) {
      setSearchParams({ code: visibleCodes[0] }, { replace: true })
    }
  }, [visibleCodes, selectedCode, setSearchParams, isNarrow])

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <Spin />
      </div>
    )
  }

  // 窄屏单栏主从：未选中时列表占满，选中后详情整屏替换（带返回）
  const listOnly = isNarrow && !selectedCode
  const detailOnly = isNarrow && !!selectedCode

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
        {!detailOnly && (
          <div
            className={`w-full lg:w-[300px] shrink-0 border-b lg:border-b-0 lg:border-r border-gray-800 flex flex-col min-h-0 ${
              listOnly ? 'flex-1' : 'max-h-64 lg:max-h-none'
            }`}
          >
            <WatchlistStockList
              groups={groups ?? []}
              activeGroupId={activeGroupId}
              quotesByCode={quotesByCode}
              selectedCode={selectedCode}
              onSelect={selectCode}
            />
          </div>
        )}
        {!listOnly && (
          <div className="flex-1 min-w-0 min-h-0 flex flex-col">
            {detailOnly && (
              <div className="shrink-0 border-b border-gray-800">
                <Button
                  type="text"
                  size="small"
                  icon={<ArrowLeftOutlined />}
                  onClick={() => setSearchParams({}, { replace: true })}
                  className="!text-gray-300"
                >
                  返回列表
                </Button>
              </div>
            )}
            {selectedCode ? (
              <div className="flex-1 min-h-0">
                <StockDetailContent stockCode={selectedCode} />
              </div>
            ) : (
              <div className="h-full flex items-center justify-center">
                <Empty description="暂无自选股，可通过顶部搜索或截图导入添加" />
              </div>
            )}
          </div>
        )}
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
