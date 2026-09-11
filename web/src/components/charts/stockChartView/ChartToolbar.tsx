import {
  CheckOutlined,
  DownOutlined,
  FullscreenExitOutlined,
  FullscreenOutlined,
  SettingOutlined,
} from '@ant-design/icons'
import { Button, Dropdown, Popover, Radio } from 'antd'
import { useNavigate } from 'react-router-dom'

import { useSettingsStore } from '@/stores/settings'

import { BORDER_COLOR, PERIOD_OPTIONS } from './constants'
import type { StockChartViewIndicators } from './StockChartView'

const INDICATOR_OPTIONS: { key: keyof StockChartViewIndicators; label: string }[] = [
  { key: 'volume', label: 'VOL' },
  { key: 'ma', label: 'MA' },
  { key: 'macd', label: 'MACD' },
  { key: 'kdj', label: 'KDJ' },
]

interface ChartToolbarProps {
  period: string
  onPeriodChange: (period: string) => void
  indicators: StockChartViewIndicators
  onToggleIndicator: (key: keyof StockChartViewIndicators) => void
  /** 周期选项子集（缺省展示个股全部周期，如板块仅 日K/周K）。 */
  periodOptions?: { label: string; value: string }[]
  layoutToggle?: { value: boolean; onChange: (dual: boolean) => void }
  onResetZoom: () => void
  isFullscreen: boolean
  onToggleFullscreen: () => void
}

export function ChartToolbar({
  period,
  onPeriodChange,
  indicators,
  onToggleIndicator,
  periodOptions = PERIOD_OPTIONS,
  layoutToggle,
  onResetZoom,
  isFullscreen,
  onToggleFullscreen,
}: ChartToolbarProps) {
  const colorScheme = useSettingsStore((s) => s.colorScheme)
  const setColorScheme = useSettingsStore((s) => s.setColorScheme)
  const navigate = useNavigate()

  const indicatorItems = INDICATOR_OPTIONS.map((opt) => ({
    key: opt.key,
    label: (
      <span className="flex items-center justify-between gap-4">
        {opt.label}
        {indicators[opt.key] && <CheckOutlined className="text-[10px]" />}
      </span>
    ),
  }))

  const activeIndicatorLabels = INDICATOR_OPTIONS.filter(
    (opt) => indicators[opt.key],
  ).map((opt) => opt.label)

  return (
    <div
      className="flex items-center gap-2 px-2.5 shrink-0"
      style={{ height: 36, borderBottom: `1px solid ${BORDER_COLOR}` }}
    >
      <div className="flex items-center gap-0.5 rounded-md p-0.5 bg-[#1c1f26]">
        {periodOptions.map((opt) => (
          <button
            key={opt.value}
            type="button"
            onClick={() => onPeriodChange(opt.value)}
            className={`px-2.5 py-[3px] text-xs rounded transition-colors ${
              period === opt.value
                ? 'font-medium bg-[rgba(94,106,210,0.12)] text-[#5e6ad2]'
                : 'text-[#8a8f98] hover:text-[#f0f1f5]'
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>
      <span className="w-px h-4 bg-[#23262d]" />
      <Dropdown
        trigger={['click']}
        menu={{
          items: indicatorItems,
          onClick: ({ key }) => onToggleIndicator(key as keyof StockChartViewIndicators),
        }}
      >
        <button
          type="button"
          className="flex items-center gap-1 px-2 py-[3px] text-xs text-[#8a8f98] border border-[#23262d] rounded transition-colors hover:text-[#f0f1f5] hover:border-[#2e323c]"
        >
          {activeIndicatorLabels.length > 0
            ? `指标：${activeIndicatorLabels.join(' · ')}`
            : '指标'}
          <DownOutlined className="!text-[9px]" />
        </button>
      </Dropdown>

      <div className="ml-auto flex items-center gap-1.5">
        {layoutToggle && (
          <div className="flex items-center gap-0.5 rounded-md p-0.5 bg-[#1c1f26]">
            {([true, false] as const).map((v) => (
              <button
                key={v ? 'dual' : 'single'}
                type="button"
                onClick={() => layoutToggle.onChange(v)}
                className={`px-2 py-[3px] text-xs rounded transition-colors ${
                  layoutToggle.value === v
                    ? 'font-medium bg-[rgba(94,106,210,0.12)] text-[#5e6ad2]'
                    : 'text-[#8a8f98] hover:text-[#f0f1f5]'
                }`}
              >
                {v ? '双图' : '单图'}
              </button>
            ))}
          </div>
        )}
        <Popover
          trigger="click"
          placement="bottomRight"
          content={
            <div className="w-44 space-y-2.5">
              <div>
                <div className="text-xs text-[#8a8f98] mb-1.5">涨跌配色</div>
                <Radio.Group
                  size="small"
                  value={colorScheme}
                  onChange={(e) => setColorScheme(e.target.value)}
                >
                  <Radio.Button value="cn">红涨绿跌</Radio.Button>
                  <Radio.Button value="us">绿涨红跌</Radio.Button>
                </Radio.Group>
              </div>
              <Button size="small" block onClick={onResetZoom}>
                复位缩放窗口
              </Button>
              <Button size="small" block onClick={() => navigate('/settings')}>
                更多设置
              </Button>
            </div>
          }
        >
          <button
            type="button"
            title="图表设置"
            className="flex items-center justify-center w-[26px] h-[26px] rounded text-[#8a8f98] transition-colors hover:bg-[#1c1f26] hover:text-[#f0f1f5]"
          >
            <SettingOutlined className="!text-[13px]" />
          </button>
        </Popover>
        <button
          type="button"
          title={isFullscreen ? '退出全屏' : '全屏'}
          onClick={onToggleFullscreen}
          className="flex items-center justify-center w-[26px] h-[26px] rounded text-[#8a8f98] transition-colors hover:bg-[#1c1f26] hover:text-[#f0f1f5]"
        >
          {isFullscreen ? (
            <FullscreenExitOutlined className="!text-[13px]" />
          ) : (
            <FullscreenOutlined className="!text-[13px]" />
          )}
        </button>
      </div>
    </div>
  )
}
