/** 任务日志：左任务目录（业务分类折叠/搜索/常用置顶/手动触发，宽度可拖拽调节）+ 右执行日志双栏。 */

import { Card, message } from 'antd'
import {
  useEffect,
  useState,
  type CSSProperties,
  type MouseEvent as ReactMouseEvent,
} from 'react'
import { useSearchParams } from 'react-router-dom'

import { useCollectorTaskCatalog, useRunCollectorTask } from '@/hooks/useCollectorAdmin'
import { getTaskLabel } from '@/utils/collectorTaskLabels'
import { TASK_CATEGORY_META } from '@/utils/taskCategoryMeta'
import type {
  CollectorTaskCatalogItem,
  CollectorTaskName,
  CollectorTaskOption,
  CollectorTaskRunOptions,
} from '@ai-invest/shared'

import {
  clearCatalogWidth,
  getCatalogWidth,
  getCollapsedGroups,
  getFrequentTasks,
  pushFrequentTask,
  setCatalogWidth,
  setCollapsedGroups,
} from './collectorPrefs'
import { CollectorLogPanel } from './CollectorLogPanel'
import { CollectorTaskCatalogPanel } from './CollectorTaskCatalogPanel'
import { CollectorTaskModal } from './CollectorTaskModal'

/** 默认全部分类组收起，仅常用组展开。 */
const DEFAULT_COLLAPSED_GROUPS = Object.keys(TASK_CATEGORY_META)

/** 目录栏宽度边界（px）：拖拽夹取，双击分隔条恢复默认。 */
const DEFAULT_CATALOG_WIDTH = 400
const MIN_CATALOG_WIDTH = 280
const MAX_CATALOG_WIDTH = 640

const clampCatalogWidth = (width: number) =>
  Math.min(MAX_CATALOG_WIDTH, Math.max(MIN_CATALOG_WIDTH, width))

export function Collector() {
  const [searchParams, setSearchParams] = useSearchParams()
  const taskNameFilter = searchParams.get('taskName')
  const sourceFilter = searchParams.get('source')
  const { data: catalog } = useCollectorTaskCatalog()
  const runMutation = useRunCollectorTask()

  const [modalOpen, setModalOpen] = useState(false)
  const [selectedTask, setSelectedTask] = useState<CollectorTaskOption | null>(null)
  const [frequentTasks, setFrequentTasks] = useState<string[]>(() => getFrequentTasks())
  const [collapsedGroups, setCollapsedGroupsState] = useState<string[] | null>(() =>
    getCollapsedGroups(),
  )
  const [catalogWidth, setCatalogWidthState] = useState<number | null>(() => getCatalogWidth())
  const [resizing, setResizing] = useState(false)
  const effectiveCatalogWidth = clampCatalogWidth(catalogWidth ?? DEFAULT_CATALOG_WIDTH)

  // 拖拽期间锁定光标与禁选文本，防止划过文字时选中/光标抖动
  useEffect(() => {
    if (!resizing) return
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    return () => {
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
  }, [resizing])

  const startResize = (event: ReactMouseEvent) => {
    event.preventDefault()
    const startX = event.clientX
    const startWidth = effectiveCatalogWidth
    const apply = (clientX: number) => {
      const next = clampCatalogWidth(startWidth + (clientX - startX))
      setCatalogWidthState(next)
      setCatalogWidth(next)
    }
    const onMove = (e: MouseEvent) => apply(e.clientX)
    const onUp = (e: MouseEvent) => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
      setResizing(false)
      apply(e.clientX)
    }
    setResizing(true)
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }

  const resetCatalogWidth = () => {
    clearCatalogWidth()
    setCatalogWidthState(null)
  }

  const catalogItems: CollectorTaskCatalogItem[] = catalog?.items ?? []
  const taskOptions: CollectorTaskOption[] = catalogItems.map((item) => ({
    key: item.name,
    label: item.label,
  }))
  const effectiveCollapsed = collapsedGroups ?? DEFAULT_COLLAPSED_GROUPS

  const handleCollapsedGroupsChange = (keys: string[]) => {
    setCollapsedGroupsState(keys)
    setCollapsedGroups(keys)
  }

  const handleOpenModal = (item: CollectorTaskCatalogItem) => {
    setSelectedTask({ key: item.name as CollectorTaskName, label: item.label })
    setModalOpen(true)
  }

  const handleFilterChange = (patch: { taskName?: string | null; source?: string | null }) => {
    const next = new URLSearchParams(searchParams)
    if (patch.taskName !== undefined) {
      if (patch.taskName) next.set('taskName', patch.taskName)
      else next.delete('taskName')
    }
    if (patch.source !== undefined) {
      if (patch.source) next.set('source', patch.source)
      else next.delete('source')
    }
    setSearchParams(next, { replace: true })
  }

  const handleRun = async (taskName: CollectorTaskName, options: CollectorTaskRunOptions) => {
    try {
      const body = {
        preferred_source: options.preferredSource || undefined,
        symbols: options.symbols,
        period: options.period || undefined,
        start_date: options.startDate || undefined,
        end_date: options.endDate || undefined,
        sector_type: options.sectorType || undefined,
        indicators: options.indicators,
        report_types: options.reportTypes,
        report_date: options.reportDate || undefined,
        trade_date: options.tradeDate || undefined,
      }
      await runMutation.mutateAsync({ taskName, body })
      pushFrequentTask(taskName)
      setFrequentTasks(getFrequentTasks())
      message.info(`「${getTaskLabel(taskName)}」已派发到采集队列，执行状态见右侧日志`)
      setModalOpen(false)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '触发失败')
    }
  }

  return (
    <div
      className={`flex flex-col gap-3 xl:flex-row xl:items-start ${resizing ? 'select-none' : ''}`}
    >
      <Card
        variant="borderless"
        title="任务目录"
        className="w-full xl:w-[var(--catalog-w)] xl:shrink-0"
        style={{ '--catalog-w': `${effectiveCatalogWidth}px` } as CSSProperties}
        styles={{ body: { paddingTop: 12 } }}
      >
        <CollectorTaskCatalogPanel
          items={catalogItems}
          frequentTasks={frequentTasks}
          collapsedGroups={effectiveCollapsed}
          onCollapsedGroupsChange={handleCollapsedGroupsChange}
          onOpenTask={handleOpenModal}
        />
      </Card>

      <div
        role="separator"
        aria-orientation="vertical"
        title="拖动调整目录宽度，双击恢复默认"
        onMouseDown={startResize}
        onDoubleClick={resetCatalogWidth}
        className="hidden w-1.5 shrink-0 cursor-col-resize self-stretch rounded-full bg-white/[0.04] transition-colors hover:bg-white/15 xl:block"
      />

      <Card variant="borderless" title="执行日志" className="w-full min-w-0 flex-1">
        <CollectorLogPanel
          taskNameFilter={taskNameFilter}
          sourceFilter={sourceFilter}
          taskOptions={taskOptions}
          onFilterChange={handleFilterChange}
        />
      </Card>

      <CollectorTaskModal
        open={modalOpen}
        task={selectedTask}
        onCancel={() => setModalOpen(false)}
        onSubmit={handleRun}
        loading={runMutation.isPending}
      />
    </div>
  )
}
