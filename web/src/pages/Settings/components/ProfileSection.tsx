/** 基本信息 section：头像/角色/注册登录时间展示 + 邮箱编辑弹窗。 */

import { EditOutlined } from '@ant-design/icons'
import { Button, Card, Form, Input, Modal, Tag } from 'antd'
import { useState } from 'react'

import { useMyProfile, useUpdateMyEmail } from '@/hooks/useUsers'
import { useAuthStore } from '@/stores/auth'
import { formatDate, formatDateTime } from '@/utils/formatters'
import { DescRow, HintBox } from './SettingHints'

export function ProfileSection() {
  const { user } = useAuthStore()
  const profileQ = useMyProfile()
  const updateEmail = useUpdateMyEmail()
  const [editOpen, setEditOpen] = useState(false)
  const [editForm] = Form.useForm<{ email: string }>()
  const profile = profileQ.data

  const openEdit = () => {
    editForm.setFieldsValue({ email: user?.email ?? profile?.email ?? '' })
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

  return (
    <>
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
            value={profile?.lastLoginAt ? formatDateTime(profile.lastLoginAt) : '-'}
          />
        </div>

        <HintBox>
          用户名与角色由管理员维护，如需变更请联系管理员；邮箱用于账号找回与重要通知。
        </HintBox>
      </Card>

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
    </>
  )
}
