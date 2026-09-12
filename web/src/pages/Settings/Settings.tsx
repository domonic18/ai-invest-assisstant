import { EditOutlined, LogoutOutlined, SettingOutlined } from '@ant-design/icons'
import { App, Button, Card, Form, Input, Modal, Space, Tag, Typography } from 'antd'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { MovingAverageConfig } from '@ai-invest/shared'

import { useChangeMyPassword, useMyProfile, useUpdateMyEmail } from '@/hooks/useUsers'
import { useAuthStore } from '@/stores/auth'
import { useColorScheme, useSettingsStore } from '@/stores/settings'
import { semanticColors } from '@/theme/colors'
import { formatDate, formatDateTime } from '@/utils/formatters'
import { MovingAverageConfigList } from './components/MovingAverageConfigList'
import { TrackedIndexSettings } from './components/TrackedIndexSettings'
import {
  MAX_MA_COUNT,
  nextDefaultColor,
  nextDefaultPeriod,
  sortByPeriod,
} from './utils'

const SECTIONS = [
  { key: 'profile', label: '基本信息' },
  { key: 'appearance', label: '外观偏好' },
  { key: 'indexes', label: '跟踪指数' },
  { key: 'security', label: '账号安全' },
] as const

type SectionKey = (typeof SECTIONS)[number]['key']

const SCHEME_OPTIONS = [
  { value: 'cn', name: '红涨绿跌', note: '国内习惯' },
  { value: 'us', name: '绿涨红跌', note: '国际习惯' },
] as const

interface PasswordFormValues {
  currentPassword: string
  newPassword: string
  confirmPassword: string
}

function DescRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between text-xs py-1">
      <span className="text-[#5c616e]">{label}</span>
      <span className="font-mono text-[#8a8f98]">{value}</span>
    </div>
  )
}

function HintBox({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-3 rounded-md bg-[#181a21] border border-[#23262d] px-2.5 py-2 text-[11px] leading-relaxed text-[#8a8f98]">
      {children}
    </div>
  )
}

export function Settings() {
  const navigate = useNavigate()
  const { message } = App.useApp()
  const { user, logout } = useAuthStore()
  const colorScheme = useColorScheme()
  const setColorScheme = useSettingsStore((state) => state.setColorScheme)
  const userSettings = useSettingsStore((state) => state.userSettings)
  const updateMaConfigs = useSettingsStore((state) => state.updateMaConfigs)
  const settingsError = useSettingsStore((state) => state.settingsError)

  const profileQ = useMyProfile()
  const updateEmail = useUpdateMyEmail()
  const changePassword = useChangeMyPassword()

  const [activeSection, setActiveSection] = useState<SectionKey>('profile')
  const [editOpen, setEditOpen] = useState(false)
  const [pwdForm] = Form.useForm<PasswordFormValues>()
  const [editForm] = Form.useForm<{ email: string }>()

  const [draftConfigs, setDraftConfigs] = useState<MovingAverageConfig[]>(
    () => userSettings.maConfigs,
  )
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setDraftConfigs(userSettings.maConfigs)
  }, [userSettings.maConfigs])

  useEffect(() => {
    const sections = SECTIONS.map((s) => document.getElementById(`sec-${s.key}`)).filter(
      (el): el is HTMLElement => el != null,
    )
    if (!sections.length) return
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveSection(entry.target.id.replace('sec-', '') as SectionKey)
          }
        }
      },
      { rootMargin: '-10% 0px -75% 0px' },
    )
    sections.forEach((section) => observer.observe(section))
    return () => observer.disconnect()
  }, [])

  const openEdit = () => {
    editForm.setFieldsValue({ email: user?.email ?? profileQ.data?.email ?? '' })
    setEditOpen(true)
  }

  const handleSaveEmail = async () => {
    const values = await editForm.validateFields()
    try {
      const updated = await updateEmail.mutateAsync(values.email)
      useAuthStore.getState().setUser(updated)
      setEditOpen(false)
    } catch {
      // 失败已由 mutation onError 提示
    }
  }

  const handleChangePassword = async (values: PasswordFormValues) => {
    try {
      await changePassword.mutateAsync({
        currentPassword: values.currentPassword,
        newPassword: values.newPassword,
      })
      message.success('密码已修改，请重新登录')
      logout()
      navigate('/login', { replace: true })
    } catch {
      // 失败已由 mutation onError 提示
    }
  }

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
  const profile = profileQ.data

  return (
    <div className="max-w-4xl">
      <Typography.Title level={4} className="!mb-0">个人设置</Typography.Title>
      <Typography.Paragraph type="secondary" className="!mt-1 !mb-4 text-xs">
        账号信息、外观偏好与账号安全集中配置
      </Typography.Paragraph>

      <nav className="md:hidden flex gap-2 overflow-x-auto pb-2 mb-2">
        {SECTIONS.map((section) => (
          <a
            key={section.key}
            href={`#sec-${section.key}`}
            className={`shrink-0 px-3 py-1.5 rounded-full text-xs border transition-colors ${
              activeSection === section.key
                ? 'border-[#5e6ad2] text-[#5e6ad2] bg-[rgba(94,106,210,0.10)]'
                : 'border-[#23262d] text-[#8a8f98]'
            }`}
          >
            {section.label}
          </a>
        ))}
      </nav>

      <div className="flex items-start gap-6">
        <nav className="hidden md:flex flex-col gap-0.5 w-36 shrink-0 sticky top-0">
          <div className="text-[11px] tracking-wider text-[#5c616e] px-3 mb-1.5">设置</div>
          {SECTIONS.map((section) => (
            <a
              key={section.key}
              href={`#sec-${section.key}`}
              className={`block px-3 py-1.5 rounded text-sm border-l-2 transition-colors ${
                activeSection === section.key
                  ? 'text-[#5e6ad2] bg-[rgba(94,106,210,0.10)] border-[#5e6ad2] font-medium'
                  : 'text-[#8a8f98] border-transparent hover:text-[#f0f1f5] hover:bg-[#14161c]'
              }`}
            >
              {section.label}
            </a>
          ))}
        </nav>

        <div className="flex-1 min-w-0 space-y-5">
          <section id="sec-profile" className="scroll-mt-4">
            <Card
              variant="borderless"
              title="基本信息"
              extra={
                <Button size="small" icon={<EditOutlined />} onClick={openEdit}>
                  编辑
                </Button>
              }
            >
              <div className="flex items-center gap-3">
                <div
                  className="w-12 h-12 rounded-full flex items-center justify-center text-lg font-semibold text-white shrink-0"
                  style={{ background: 'linear-gradient(135deg, #5e6ad2, #9d7ff5)' }}
                >
                  {(user?.username ?? 'U').charAt(0).toUpperCase()}
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-[15px] font-semibold text-[#f0f1f5] truncate">
                      {user?.username ?? '-'}
                    </span>
                    <Tag bordered={false} color={user?.isAdmin ? 'purple' : 'default'}>
                      {user?.isAdmin ? '管理员' : '普通用户'}
                    </Tag>
                  </div>
                  <div className="text-xs text-[#8a8f98] mt-0.5 truncate">
                    {user?.email ?? profile?.email ?? '-'}
                  </div>
                </div>
              </div>

              <div className="mt-4">
                <DescRow label="注册时间" value={formatDate(profile?.createdAt)} />
                <DescRow
                  label="上次登录"
                  value={
                    profile?.lastLoginAt ? formatDateTime(profile.lastLoginAt) : '-'
                  }
                />
              </div>

              <HintBox>
                用户名与角色由管理员维护，如需变更请联系管理员；邮箱用于账号找回与重要通知。
              </HintBox>
            </Card>
          </section>

          <section id="sec-appearance" className="scroll-mt-4 space-y-5">
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
          </section>

          <section id="sec-indexes" className="scroll-mt-4">
            <Card
              variant="borderless"
              title="跟踪指数"
              extra={<span className="text-xs text-[#5c616e]">默认显示全部</span>}
            >
              <TrackedIndexSettings />
              <HintBox>
                控制工作台「市场指数」与宏观指数页展示哪些指标；A 股指数 / ETF
                支持自定义添加（历史行情自动回填），全球指标暂限内置清单。保存在<b>服务端</b>（随账号漫游）；全部勾选即恢复默认。
              </HintBox>
            </Card>
          </section>

          <section id="sec-security" className="scroll-mt-4 space-y-5">
            <Card variant="borderless" title="修改密码">
              <Form
                form={pwdForm}
                layout="vertical"
                className="max-w-sm"
                onFinish={handleChangePassword}
              >
                <Form.Item
                  name="currentPassword"
                  label="当前密码"
                  rules={[{ required: true, message: '请输入当前密码' }]}
                >
                  <Input.Password placeholder="输入当前密码" autoComplete="current-password" />
                </Form.Item>
                <Form.Item
                  name="newPassword"
                  label="新密码"
                  rules={[
                    { required: true, message: '请输入新密码' },
                    { min: 6, message: '新密码至少 6 位' },
                    { max: 128, message: '新密码不超过 128 位' },
                  ]}
                >
                  <Input.Password placeholder="至少 6 位" autoComplete="new-password" />
                </Form.Item>
                <Form.Item
                  name="confirmPassword"
                  label="确认新密码"
                  dependencies={['newPassword']}
                  rules={[
                    { required: true, message: '请再次输入新密码' },
                    ({ getFieldValue }) => ({
                      validator(_, value) {
                        if (!value || getFieldValue('newPassword') === value) {
                          return Promise.resolve()
                        }
                        return Promise.reject(new Error('两次输入的新密码不一致'))
                      },
                    }),
                  ]}
                >
                  <Input.Password placeholder="再次输入新密码" autoComplete="new-password" />
                </Form.Item>
                <div className="flex justify-end">
                  <Button type="primary" htmlType="submit" loading={changePassword.isPending}>
                    修改密码
                  </Button>
                </div>
              </Form>
              <HintBox>修改成功后将自动退出当前登录，需使用新密码重新登录。</HintBox>
            </Card>

            <Card
              variant="borderless"
              className="!border !border-[rgba(248,81,73,0.25)]"
              title="危险操作"
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-[13px] font-medium text-[#f0f1f5]">退出登录</div>
                  <div className="text-xs text-[#5c616e] mt-0.5">
                    退出当前账号，返回登录页
                  </div>
                </div>
                <Button danger icon={<LogoutOutlined />} onClick={handleLogout}>
                  退出登录
                </Button>
              </div>
            </Card>
          </section>
        </div>
      </div>

      <Modal
        title="编辑基本信息"
        open={editOpen}
        onOk={() => void handleSaveEmail()}
        onCancel={() => setEditOpen(false)}
        confirmLoading={updateEmail.isPending}
        okText="保存"
        cancelText="取消"
        destroyOnClose
      >
        <Form form={editForm} layout="vertical" preserve={false}>
          <Form.Item label="用户名">
            <Input value={user?.username} disabled />
          </Form.Item>
          <Form.Item
            name="email"
            label="邮箱"
            rules={[
              { required: true, message: '请输入邮箱' },
              { type: 'email', message: '邮箱格式不正确' },
              { max: 100, message: '邮箱不超过 100 字符' },
            ]}
          >
            <Input placeholder="name@example.com" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
