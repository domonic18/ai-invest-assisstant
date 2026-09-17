import { Form, Input, InputNumber, Modal, Select } from 'antd'
import { useEffect } from 'react'
import type { ApiSocialAccountAdmin } from '@ai-invest/shared'

const CATEGORY_OPTIONS = [
  { label: '财经KOL', value: 'finance_kol' },
  { label: '宏观政策', value: 'macro_policy' },
  { label: '行业', value: 'industry' },
]

interface SocialAccountModalProps {
  open: boolean
  editing: ApiSocialAccountAdmin | null
  loading: boolean
  onCancel: () => void
  onSubmit: (values: {
    secUidOrUrl?: string
    alias: string
    category: string
    pollIntervalMinutes: number
    remark?: string | null
  }) => void
}

interface AccountFormValues {
  secUidOrUrl?: string
  alias: string
  category: string
  pollIntervalMinutes: number
  remark?: string
}

export function SocialAccountModal({
  open,
  editing,
  loading,
  onCancel,
  onSubmit,
}: SocialAccountModalProps) {
  const [form] = Form.useForm<AccountFormValues>()

  useEffect(() => {
    if (!open) return
    form.resetFields()
    if (editing) {
      form.setFieldsValue({
        alias: editing.alias,
        category: editing.category,
        pollIntervalMinutes: editing.pollIntervalMinutes,
        remark: editing.remark ?? undefined,
      })
    } else {
      form.setFieldsValue({
        category: 'finance_kol',
        pollIntervalMinutes: 60,
      })
    }
  }, [open, editing, form])

  return (
    <Modal
      title={editing ? `编辑账号：${editing.alias}` : '登记追踪账号'}
      open={open}
      onCancel={onCancel}
      destroyOnHidden
      confirmLoading={loading}
      onOk={() => form.submit()}
    >
      <Form
        form={form}
        layout="vertical"
        onFinish={(values) =>
          onSubmit({
            ...(editing ? {} : { secUidOrUrl: values.secUidOrUrl ?? '' }),
            alias: values.alias,
            category: values.category,
            pollIntervalMinutes: values.pollIntervalMinutes,
            remark: values.remark || null,
          })
        }
      >
        {!editing && (
          <Form.Item
            name="secUidOrUrl"
            label="主页链接 / sec_uid"
            rules={[{ required: true, message: '请输入抖音主页链接或 sec_uid' }]}
            extra="支持主页分享短链、标准主页链接或裸 sec_uid"
          >
            <Input placeholder="https://v.douyin.com/... 或 MS4wLjABAAAA..." />
          </Form.Item>
        )}
        <Form.Item
          name="alias"
          label="账号别名"
          rules={[{ required: true, message: '请输入账号别名' }]}
        >
          <Input placeholder="如 财经大V-A" maxLength={64} />
        </Form.Item>
        <Form.Item name="category" label="分类">
          <Select options={CATEGORY_OPTIONS} />
        </Form.Item>
        <Form.Item
          name="pollIntervalMinutes"
          label="轮询间隔（分钟）"
          rules={[{ required: true, message: '请输入轮询间隔' }]}
          extra="最低 5 分钟"
        >
          <InputNumber min={5} max={1440} style={{ width: 160 }} />
        </Form.Item>
        <Form.Item name="remark" label="备注">
          <Input.TextArea rows={2} placeholder="选填" maxLength={200} />
        </Form.Item>
      </Form>
    </Modal>
  )
}
