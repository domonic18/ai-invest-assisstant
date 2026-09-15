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
        message="请从已登录抖音的浏览器复制完整 Cookie 请求头"
        description="F12 → 网络(Network) → 刷新页面 → 点首个 www.douyin.com 请求 → 请求标头(Request Headers) → 复制 Cookie 行的整串值。仅 ttwid 一两个键过不了作品接口风控（采集拿不到数据）；缺少 ttwid 或键值对少于 3 组会被拒绝。相同 ttwid 重复导入会覆盖旧值。"
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
              validator: (_, v: string) => {
                if (!v?.trim()) return Promise.resolve()
                if (!v.includes('ttwid='))
                  return Promise.reject(new Error('Cookie 串中未检测到 ttwid'))
                const pairs = v.split(';').filter((p) => p.trim()).length
                if (pairs < 3)
                  return Promise.reject(
                    new Error(
                      `只有 ${pairs} 组键值：请按上方指引复制完整 Cookie 请求头（通常数十组）`,
                    ),
                  )
                return Promise.resolve()
              },
            },
          ]}
        >
          <Input.TextArea
            rows={6}
            style={{ fontFamily: 'monospace' }}
            placeholder="ttwid=xxx; UIFID=xxx; s_v_web_id=xxx; ..."
            onChange={(e) => setValue(e.target.value)}
          />
        </Form.Item>
        <Typography.Paragraph type="secondary" className="!mb-0">
          Cookie 含登录态，仅加密存库用于采集，不会展示或导出。
        </Typography.Paragraph>
      </Form>
    </Modal>
  )
}
