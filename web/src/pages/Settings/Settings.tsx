import { LogoutOutlined, SettingOutlined } from '@ant-design/icons'
import { Button, Card, Descriptions, Space, Switch, Typography, message } from 'antd'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { MovingAverageConfig } from '@ai-invest/shared'

import { useAuthStore } from '@/stores/auth'
import { useColorScheme, useSettingsStore } from '@/stores/settings'
import { MovingAverageConfigList } from './components/MovingAverageConfigList'
import {
  MAX_MA_COUNT,
  nextDefaultColor,
  nextDefaultPeriod,
  sortByPeriod,
} from './utils'

export function Settings() {
  const navigate = useNavigate()
  const { user, logout } = useAuthStore()
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

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

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
    <div className="space-y-6 max-w-2xl">
      <Typography.Title level={4} className="!mb-0">用户设置</Typography.Title>

      <Card title="基本信息" variant="borderless">
        <Descriptions column={1} bordered>
          <Descriptions.Item label="用户名">{user?.username || '-'}</Descriptions.Item>
          <Descriptions.Item label="邮箱">{user?.email || '-'}</Descriptions.Item>
          <Descriptions.Item label="角色">{user?.isAdmin ? '管理员' : '普通用户'}</Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title="行情配色" variant="borderless">
        <div className="flex items-center justify-between">
          <div>
            <div className="font-medium">红涨绿跌（国内习惯）</div>
            <Typography.Text type="secondary" className="text-xs">
              开启后上涨显示为红色、下跌显示为绿色；关闭则为绿涨红跌（国际习惯）。全站生效。
            </Typography.Text>
          </div>
          <Switch
            checked={colorScheme === 'cn'}
            onChange={(checked) => setColorScheme(checked ? 'cn' : 'us')}
          />
        </div>
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
      </Card>

      <Card title="账号安全" variant="borderless">
        <Space>
          <Button type="primary" danger icon={<LogoutOutlined />} onClick={handleLogout}>
            退出登录
          </Button>
        </Space>
      </Card>
    </div>
  )
}
