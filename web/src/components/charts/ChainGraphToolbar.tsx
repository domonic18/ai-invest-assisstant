import {
  FilterFilled,
  FullscreenExitOutlined,
  FullscreenOutlined,
  MinusOutlined,
  PlusOutlined,
  SearchOutlined,
  ZoomOutOutlined,
} from '@ant-design/icons'
import { Checkbox, Input, Radio, Space, Tooltip } from 'antd'

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
    <div className="absolute left-3 top-3 z-10 flex flex-wrap items-center gap-3 rounded-lg border border-[#e2e8f0] bg-white p-2 shadow-sm">
      <Space>
        <Tooltip title="放大">
          <button
            type="button"
            onClick={onZoomIn}
            className="flex h-7 w-7 items-center justify-center rounded hover:bg-gray-100"
          >
            <PlusOutlined />
          </button>
        </Tooltip>
        <Tooltip title="缩小">
          <button
            type="button"
            onClick={onZoomOut}
            className="flex h-7 w-7 items-center justify-center rounded hover:bg-gray-100"
          >
            <MinusOutlined />
          </button>
        </Tooltip>
        <Tooltip title="适配画布">
          <button
            type="button"
            onClick={onFitView}
            className="flex h-7 w-7 items-center justify-center rounded hover:bg-gray-100"
          >
            <ZoomOutOutlined rotate={90} />
          </button>
        </Tooltip>
        <Tooltip title={isFullscreen ? '退出全屏' : '全屏查看'}>
          <button
            type="button"
            onClick={onToggleFullscreen}
            className="flex h-7 w-7 items-center justify-center rounded hover:bg-gray-100"
          >
            {isFullscreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
          </button>
        </Tooltip>
      </Space>

      <div className="h-5 w-px bg-[#e2e8f0]" />

      <Space align="center">
        <FilterFilled className="text-gray-400" />
        <Checkbox
          checked={nodeFilters.upstream}
          onChange={(e) => updateFilter('upstream', e.target.checked)}
        >
          上游
        </Checkbox>
        <Checkbox
          checked={nodeFilters.midstream}
          onChange={(e) => updateFilter('midstream', e.target.checked)}
        >
          中游
        </Checkbox>
        <Checkbox
          checked={nodeFilters.downstream}
          onChange={(e) => updateFilter('downstream', e.target.checked)}
        >
          下游
        </Checkbox>
      </Space>

      <div className="h-5 w-px bg-[#e2e8f0]" />

      <Space align="center">
        <span className="text-sm text-gray-500">边关键性</span>
        <Radio.Group
          value={edgeFilter}
          onChange={(e) => onEdgeFilterChange(e.target.value)}
          optionType="button"
          buttonStyle="solid"
          size="small"
        >
          <Radio.Button value="all">全部</Radio.Button>
          <Radio.Button value="high">高</Radio.Button>
          <Radio.Button value="medium">中</Radio.Button>
          <Radio.Button value="low">低</Radio.Button>
        </Radio.Group>
      </Space>

      <div className="h-5 w-px bg-[#e2e8f0]" />

      <Input.Search
        value={searchKeyword}
        onChange={(e) => onSearchChange(e.target.value)}
        onSearch={onSearch}
        placeholder="搜索环节/公司"
        allowClear
        size="small"
        style={{ width: 160 }}
        enterButton={<SearchOutlined />}
      />
    </div>
  )
}
