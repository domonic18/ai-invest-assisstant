import { App, Form, Input, InputNumber, Modal, Radio, Space } from 'antd'
import { useState } from 'react'

import {
  useAdjustUserQuota,
  useApproveUser,
  useRejectUser,
} from '@/hooks/useAdminAccount'

/** 审批弹窗所需的最小用户形状（AdminUser 与待审申请均满足） */
interface ApprovalTarget {
  id: number
  username: string
}

/** 配额弹窗额外展示字段（可选） */
interface QuotaTarget extends ApprovalTarget {
  remainingQuota?: number | null
}

/** 审批通过弹窗：可设初始配额（留空取全局默认） */
export function ApproveModal({
  user,
  onClose,
}: {
  user: ApprovalTarget | null
  onClose: () => void
}) {
  const { message } = App.useApp()
  const [form] = Form.useForm<{ initialQuotaTokens?: number | null }>()
  const mutation = useApproveUser()

  const handleOk = async () => {
    if (!user) return
    const values = await form.validateFields()
    try {
      await mutation.mutateAsync({
        id: user.id,
        data: { initialQuotaTokens: values.initialQuotaTokens ?? null },
      })
      message.success(`已通过 ${user.username} 的注册申请`)
      onClose()
    } catch (err) {
      message.error(err instanceof Error ? err.message : '操作失败')
    }
  }

  return (
    <Modal
      title={`通过申请 - ${user?.username || ''}`}
      open={!!user}
      onCancel={onClose}
      onOk={handleOk}
      confirmLoading={mutation.isPending}
      destroyOnClose
    >
      <Form form={form} layout="vertical" preserve={false}>
        <Form.Item
          name="initialQuotaTokens"
          label="初始配额（tokens，留空取全局默认 10 万）"
          rules={[{ type: 'number', min: 1 }]}
        >
          <InputNumber
            className="w-full"
            placeholder="100000"
            step={10000}
            min={1}
          />
        </Form.Item>
      </Form>
    </Modal>
  )
}

/** 驳回申请弹窗：原因必填 */
export function RejectModal({
  user,
  onClose,
}: {
  user: ApprovalTarget | null
  onClose: () => void
}) {
  const { message } = App.useApp()
  const [form] = Form.useForm<{ reason: string }>()
  const mutation = useRejectUser()

  const handleOk = async () => {
    if (!user) return
    const values = await form.validateFields()
    try {
      await mutation.mutateAsync({ id: user.id, data: { reason: values.reason } })
      message.success(`已驳回 ${user.username} 的申请（该用户名可重新申请）`)
      onClose()
    } catch (err) {
      message.error(err instanceof Error ? err.message : '操作失败')
    }
  }

  return (
    <Modal
      title={`驳回申请 - ${user?.username || ''}`}
      open={!!user}
      onCancel={onClose}
      onOk={handleOk}
      confirmLoading={mutation.isPending}
      destroyOnClose
    >
      <Form form={form} layout="vertical" preserve={false}>
        <Form.Item
          name="reason"
          label="驳回原因（将展示给申请人）"
          rules={[{ required: true, message: '请填写驳回原因' }]}
        >
          <Input.TextArea rows={3} maxLength={500} showCount />
        </Form.Item>
      </Form>
    </Modal>
  )
}

interface QuotaFormValues {
  mode: 'adjust' | 'reset'
  deltaTokens?: number
}

/** 配额调整弹窗：追加/核减 或 重置为全局默认 */
export function QuotaAdjustModal({
  user,
  onClose,
}: {
  user: QuotaTarget | null
  onClose: () => void
}) {
  const { message } = App.useApp()
  const [form] = Form.useForm<QuotaFormValues>()
  const mutation = useAdjustUserQuota()
  const [mode, setMode] = useState<'adjust' | 'reset'>('adjust')

  const handleOk = async () => {
    if (!user) return
    const values = await form.validateFields()
    try {
      if (values.mode === 'reset') {
        await mutation.mutateAsync({
          id: user.id,
          data: { action: 'reset' },
        })
        message.success(`已将 ${user.username} 的配额重置为全局默认`)
      } else {
        if (values.deltaTokens == null) {
          message.error('请输入调整量（正数追加、负数核减）')
          return
        }
        await mutation.mutateAsync({
          id: user.id,
          data: { action: 'adjust', deltaTokens: values.deltaTokens },
        })
        message.success(`已调整 ${user.username} 的配额`)
      }
      onClose()
    } catch (err) {
      message.error(err instanceof Error ? err.message : '操作失败')
    }
  }

  return (
    <Modal
      title={`调整配额 - ${user?.username || ''}（当前剩余 ${
        user?.remainingQuota == null ? '不限' : user.remainingQuota.toLocaleString('zh-CN')
      }）`}
      open={!!user}
      onCancel={onClose}
      onOk={handleOk}
      confirmLoading={mutation.isPending}
      destroyOnClose
    >
      <Form
        form={form}
        layout="vertical"
        preserve={false}
        initialValues={{ mode: 'adjust' }}
        onValuesChange={(changed) => {
          if (changed.mode) setMode(changed.mode)
        }}
      >
        <Form.Item name="mode" label="操作">
          <Radio.Group>
            <Space direction="vertical">
              <Radio value="adjust">追加 / 核减（正数追加、负数核减）</Radio>
              <Radio value="reset">重置为全局默认</Radio>
            </Space>
          </Radio.Group>
        </Form.Item>
        {mode === 'adjust' && (
          <Form.Item name="deltaTokens" label="调整量（tokens）">
            <InputNumber className="w-full" step={10000} placeholder="如 50000 或 -20000" />
          </Form.Item>
        )}
      </Form>
    </Modal>
  )
}
