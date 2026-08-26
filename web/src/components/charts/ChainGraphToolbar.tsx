import {
  FilterFilled,
  FullscreenExitOutlined,
  FullscreenOutlined,
  MinusOutlined,
  PlusOutlined,
  ZoomOutOutlined,
} from '@ant-design/icons'
import { Checkbox, Input, Segmented, Space, Tooltip } from 'antd'

interface NodeFilters {
  upstream: boolean
  midstream: boolean
  downstream: boolean
}

interface ChainGraphToolbarProps {
  isFullscreen: boolean
  onToggleFullscreen: () => void
  onZoomIn: () => void
  onZoomOut: () => void
  onFitView: () => void
  nodeFilters: NodeFilters
  onNodeFiltersChange: (filters: NodeFilters) => void
  edgeFilter: 'all' | 'high' | 'medium' | 'low'
  onEdgeFilterChange: (value: 'all' | 'high' | 'medium' | 'low') => void
  searchKeyword: string
  onSearchChange: (value: string) => void
  onSearch: () => void
}

const EDGE_OPTIONS = [
  { label: '全部', value: 'all' },
  { label: '高', value: 'high' },
  { label: '中', value: 'medium' },
  { label: '低', value: 'low' },
]

export function ChainGraphToolbar({
  isFullscreen,
  onToggleFullscreen,
  onZoomIn,
  onZoomOut,
  onFitView,
  nodeFilters,
  onNodeFiltersChange,
  edgeFilter,
  onEdgeFilterChange,
  searchKeyword,
  onSearchChange,
  onSearch,
}: ChainGraphToolbarProps) {
  const updateFilter = (key: keyof NodeFilters, checked: boolean) => {
    onNodeFiltersChange({ ...nodeFilters, [key]: checked })
  }

  return (
    <div className="absolute left-3 top-3 z-10 flex flex-wrap items-center gap-3 rounded-lg border border-[#23262e] bg-[rgba(20,22,28,0.85)] p-2 shadow-lg backdrop-blur-sm">
      <Space size={4}>
        <Tooltip title="放大">
          <button
            type="button"
            onClick={onZoomIn}
            className="flex h-7 w-7 items-center justify-center rounded text-[#d1d4dc] transition-colors hover:bg-white/10"
          >
            <PlusOutlined />
          </button>
        </Tooltip>
        <Tooltip title="缩小">
          <button
            type="button"
            onClick={onZoomOut}
            className="flex h-7 w-7 items-center justify-center rounded text-[#d1d4dc] transition-colors hover:bg-white/10"
          >
            <MinusOutlined />
          </button>
        </Tooltip>
        <Tooltip title="适配画布">
          <button
            type="button"
            onClick={onFitView}
            className="flex h-7 w-7 items-center justify-center rounded text-[#d1d4dc] transition-colors hover:bg-white/10"
          >
            <ZoomOutOutlined rotate={90} />
          </button>
        </Tooltip>
        <Tooltip title={isFullscreen ? '退出全屏' : '全屏查看'}>
          <button
            type="button"
            onClick={onToggleFullscreen}
            className="flex h-7 w-7 items-center justify-center rounded text-[#d1d4dc] transition-colors hover:bg-white/10"
          >
            {isFullscreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
          </button>
        </Tooltip>
      </Space>

      <div className="h-5 w-px bg-[#23262e]" />

      <Space align="center" size={8}>
        <FilterFilled className="text-[#8c8c8c]" />
        <Checkbox
          checked={nodeFilters.upstream}
          onChange={(e) => updateFilter('upstream', e.target.checked)}
          className="text-[#d1d4dc]"
        >
          上游
        </Checkbox>
        <Checkbox
          checked={nodeFilters.midstream}
          onChange={(e) => updateFilter('midstream', e.target.checked)}
          className="text-[#d1d4dc]"
        >
          中游
        </Checkbox>
        <Checkbox
          checked={nodeFilters.downstream}
          onChange={(e) => updateFilter('downstream', e.target.checked)}
          className="text-[#d1d4dc]"
        >
          下游
        </Checkbox>
      </Space>

      <div className="h-5 w-px bg-[#23262e]" />

      <Space align="center" size={8}>
        <span className="text-sm text-[#8c8c8c]">边关键性</span>
        <Segmented
          value={edgeFilter}
          onChange={(value) =>
            onEdgeFilterChange(value as 'all' | 'high' | 'medium' | 'low')
          }
          options={EDGE_OPTIONS}
          size="small"
        />
      </Space>

      <div className="h-5 w-px bg-[#23262e]" />

      <Input.Search
        value={searchKeyword}
        onChange={(e) => onSearchChange(e.target.value)}
        onSearch={onSearch}
        placeholder="搜索环节/公司"
        allowClear
        size="small"
        style={{ width: 160 }}
        className="chain-graph-search"
      />
    </div>
  )
}
