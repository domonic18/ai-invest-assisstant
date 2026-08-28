import { Button, ColorPicker, InputNumber, Switch, Typography } from 'antd'

import { normalizeHexColor } from '@/utils/color'
import type { MovingAverageConfig } from '@ai-invest/shared'

interface MovingAverageConfigListProps {
  configs: MovingAverageConfig[]
  maxCount: number
  onUpdate: (index: number, patch: Partial<MovingAverageConfig>) => void
  onRemove: (index: number) => void
  onAdd: () => void
  onSave: () => void
  saving?: boolean
}

export function MovingAverageConfigList({
  configs,
  maxCount,
  onUpdate,
  onRemove,
  onAdd,
  onSave,
  saving = false,
}: MovingAverageConfigListProps) {
  return (
    <>
      <div className="space-y-3">
        {configs.map((cfg, index) => (
          <div
            key={`${cfg.period}-${index}`}
            className="flex items-center gap-3 p-3 rounded-lg bg-[#14161b] border border-gray-800"
          >
            <ColorPicker
              value={cfg.color}
              size="small"
              showText
              onChange={(color) =>
                onUpdate(index, { color: normalizeHexColor(color.toHexString()) })
              }
            />
            <div className="flex items-center gap-2">
              <Typography.Text className="text-xs text-gray-400">MA</Typography.Text>
              <InputNumber
                min={1}
                max={500}
                value={cfg.period}
                onChange={(value) => onUpdate(index, { period: value ?? 1 })}
                size="small"
                className="w-20"
              />
            </div>
            <div className="flex items-center gap-2 ml-2">
              <Switch
                size="small"
                checked={cfg.enabled}
                onChange={(checked) => onUpdate(index, { enabled: checked })}
              />
              <Typography.Text className="text-xs text-gray-400">
                {cfg.enabled ? '显示' : '隐藏'}
              </Typography.Text>
            </div>
            <Button
              type="text"
              danger
              size="small"
              className="ml-auto"
              onClick={() => onRemove(index)}
            >
              删除
            </Button>
          </div>
        ))}
      </div>

      <div className="flex items-center justify-between mt-4">
        <Button
          type="dashed"
          onClick={onAdd}
          disabled={configs.length >= maxCount}
        >
          添加均线（最多 {maxCount} 条）
        </Button>
        <Button type="primary" loading={saving} onClick={onSave}>
          保存配置
        </Button>
      </div>

      <Typography.Text type="secondary" className="text-xs block mt-3">
        提示：此处配置的均线会同步应用到每日复盘的大盘指数日线、周线、月线等 K 线图中。
      </Typography.Text>
    </>
  )
}
