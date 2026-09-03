import { useMemo, useState } from 'react'
import { PlusOutlined } from '@ant-design/icons'
import { Button, Card, Spin } from 'antd'
import type { WatchlistGroup } from '@ai-invest/shared'

import { useWatchlistQuotes } from '@/hooks/useMarket'
import { useReorderWatchlistGroups, useWatchlistGroups } from '@/hooks/useWatchlistGroups'

import { GroupCard } from './components/GroupCard'
import { GroupFormModal } from './components/GroupFormModal'

export function Watchlist() {
  const { data: groups, isLoading } = useWatchlistGroups()
  const { data: quotes } = useWatchlistQuotes()
  const reorder = useReorderWatchlistGroups()
  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState<WatchlistGroup | null>(null)

  const quotesByCode = useMemo(
    () => new Map((quotes ?? []).map((quote) => [quote.code, quote])),
    [quotes],
  )

  return (
    <div className="p-4 md:p-6 max-w-4xl mx-auto space-y-4">
      <Card variant="borderless">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold">自选股管理</h1>
            <p className="text-xs text-gray-500 mt-1">
              开启分组的 AI 复盘后，每个交易日收盘自动生成组内个股分析
            </p>
          </div>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              setEditing(null)
              setFormOpen(true)
            }}
          >
            新建分组
          </Button>
        </div>
      </Card>

      {isLoading ? (
        <div className="flex justify-center py-10">
          <Spin />
        </div>
      ) : (
        groups?.map((group) => (
          <GroupCard
            key={group.id}
            group={group}
            groups={groups}
            quotesByCode={quotesByCode}
            onEdit={(target) => {
              setEditing(target)
              setFormOpen(true)
            }}
            onReorder={(groupIds) => reorder.mutate(groupIds)}
          />
        ))
      )}

      <GroupFormModal open={formOpen} group={editing} onClose={() => setFormOpen(false)} />
    </div>
  )
}
