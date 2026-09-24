/** 外观偏好 section：行情配色切换（本地存储）+ K 线均线配置（服务端漫游）。 */

import { SettingOutlined } from '@ant-design/icons'
import { App, Card, Space, Typography } from 'antd'
import { useEffect, useState } from 'react'
import type { MovingAverageConfig } from '@ai-invest/shared'

import { useColorScheme, useSettingsStore } from '@/stores/settings'
import { semanticColors } from '@/theme/colors'
import { MovingAverageConfigList } from './MovingAverageConfigList'
import { HintBox } from './SettingHints'
import {
  MAX_MA_COUNT,
  nextDefaultColor,
  nextDefaultPeriod,
  sortByPeriod,
} from '../utils'

const SCHEME_OPTIONS = [
  { value: 'cn', name: '红涨绿跌', note: '国内习惯' },
  { value: 'us', name: '绿涨红跌', note: '国际习惯' },
] as const

export function AppearanceSection() {
  const { message } = App.useApp()
  const colorScheme = useColorScheme()
  const setColorScheme = useSettingsStore((state) => state.setColorScheme)
  const userSettings = useSettingsStore((state) => state.userSettings)
  const updateMaConfigs = useSettingsStore((state) => state.updateMaConfigs)
  const settingsError = useSettingsStore((state) => state.settingsError)

  const [draftConfigs, setDraftConfigs] = useState<MovingAverageConfig[]>(
    () => userSettings.maConfigs,
  )
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setDraftConfigs(userSettings.maConfigs)
  }, [userSettings.maConfigs])

  const updateConfig = (index: number, patch: Partial<MovingAverageConfig>) => {
    setDraftConfigs((prev) => {
      const next = [...prev]
      next[index] = { ...next[index], ...patch }
      return sortByPeriod(next)
    })
  }

  const removeConfig = (index: number) => {
    setDraftConfigs((prev) => prev.filter((_, i) => i !== index))
  }

  const addConfig = () => {
    setDraftConfigs((prev) => {
      const next = [
        ...prev,
        {
          period: nextDefaultPeriod(prev),
          color: nextDefaultColor(prev),
          enabled: true,
        },
      ]
      return sortByPeriod(next)
    })
  }

  const handleSave = async () => {
    const valid = draftConfigs.filter((c) => c.period >= 1 && c.period <= 500)
    if (valid.length === 0) {
      message.error('请至少保留一条有效的均线配置')
      return
    }
    setSaving(true)
    try {
      await updateMaConfigs(valid)
      message.success('均线配置已保存')
    } catch {
      message.error(settingsError ?? '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const enabledCount = draftConfigs.filter((c) => c.enabled).length

  return (
    <>
      <Card
        variant="borderless"
        title="行情配色"
        extra={<span className="text-xs text-[#5c616e]">全站即时生效</span>}
      >
        <div className="grid grid-cols-2 gap-3">
          {SCHEME_OPTIONS.map((option) => {
            const active = colorScheme === option.value
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => setColorScheme(option.value)}
                className={`text-left p-3 rounded-lg border transition-colors ${
                  active
                    ? 'border-[#5e6ad2] bg-[rgba(94,106,210,0.08)]'
                    : 'border-[#23262d] hover:border-[#3a3f4b]'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="text-[13px] text-[#f0f1f5]">{option.name}</span>
                  <span className="text-[10px] text-[#5c616e]">{option.note}</span>
                  {active && (
                    <span className="ml-auto text-[10px] text-[#5e6ad2]">当前</span>
                  )}
                </div>
                <div className="mt-2 flex items-center gap-3 text-xs font-mono">
                  <span style={{ color: semanticColors.rise[option.value] }}>
                    ▲ +2.35%
                  </span>
                  <span style={{ color: semanticColors.fall[option.value] }}>
                    ▼ -1.28%
                  </span>
                </div>
              </button>
            )
          })}
        </div>
        <HintBox>
          配色偏好保存在<b>当前浏览器</b>（本地存储），不同步到账号——更换设备后需重新选择。
        </HintBox>
      </Card>

      <Card
        title={
          <Space>
            <SettingOutlined />
            <span>K 线均线配置</span>
          </Space>
        }
        variant="borderless"
        extra={
          <Typography.Text type="secondary" className="text-xs">
            已启用 {enabledCount} 条
          </Typography.Text>
        }
      >
        <MovingAverageConfigList
          configs={draftConfigs}
          maxCount={MAX_MA_COUNT}
          onUpdate={updateConfig}
          onRemove={removeConfig}
          onAdd={addConfig}
          onSave={handleSave}
          saving={saving}
        />
        <HintBox>
          均线配置保存在<b>服务端</b>（随账号漫游），同步应用于每日复盘与个股详情的日 / 周 / 月 K 线图。
        </HintBox>
      </Card>
    </>
  )
}
