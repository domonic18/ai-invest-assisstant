import { Alert, Form, Input, Modal, Typography } from 'antd'
import { useEffect, useState } from 'react'

interface CookieImportModalProps {
  open: boolean
  loading: boolean
  onCancel: () => void
  onSubmit: (cookie: string) => void
}

interface CookieFormValues {
  cookie: string
}

export function CookieImportModal({
  open,
  loading,
  onCancel,
  onSubmit,
}: CookieImportModalProps) {
  const [form] = Form.useForm<CookieFormValues>()
  const [value, setValue] = useState('')

  useEffect(() => {
    if (!open) return
    form.resetFields()
    setValue('')
  }, [open, form])

  return (
    <Modal
      title="导入抖音 Cookie"
      open={open}
      onCancel={onCancel}
      destroyOnHidden
      confirmLoading={loading}
      okText="导入"
      okButtonProps={{ disabled: !value.trim() }}
      onOk={() => form.submit()}
    >
      <Alert
        className="mb-3"
        type="warning"
        showIcon
        message="请从已登录抖音的浏览器复制完整 Cookie"
        description="Cookie 含登录态，仅加密存库用于采集，不会展示或导出。缺少 ttwid 会被拒绝；相同 ttwid 重复导入会覆盖旧值。"
      />
      <Form
        form={form}
        layout="vertical"
        onFinish={(values) => onSubmit(values.cookie)}
      >
        <Form.Item
          name="cookie"
          rules={[
            { required: true, message: '请粘贴 Cookie 串' },
            {
              validator: (_, v: string) =>
                v && v.includes('ttwid=')
                  ? Promise.resolve()
                  : Promise.reject(new Error('Cookie 串中未检测到 ttwid')),
            },
          ]}
        >
          <Input.TextArea
            rows={6}
            style={{ fontFamily: 'monospace' }}
            placeholder="ttwid=xxx; sessionid=xxx; ..."
            onChange={(e) => setValue(e.target.value)}
          />
        </Form.Item>
        <Typography.Paragraph type="secondary" className="!mb-0">
          浏览器操作：打开 douyin.com 并登录 → F12 → Application → Cookies → 全选复制。
        </Typography.Paragraph>
      </Form>
    </Modal>
  )
}
