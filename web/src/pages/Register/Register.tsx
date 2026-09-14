import { CheckCircleFilled, LockOutlined, MailOutlined, UserOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Form, Input, Spin, Typography } from 'antd'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { register } from '@/api/auth'
import { Brand } from '@/components/common/Brand'

interface RegisterFormValues {
  username: string
  email: string
  password: string
  confirmPassword: string
  applicationNote?: string
}

export function Register() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [accepted, setAccepted] = useState(false)

  const handleSubmit = async (values: RegisterFormValues) => {
    setLoading(true)
    setError(null)
    try {
      await register({
        username: values.username,
        email: values.email,
        password: values.password,
        applicationNote: values.applicationNote?.trim() || undefined,
      })
      setAccepted(true)
    } catch (err) {
      const message = err instanceof Error ? err.message : '注册失败，请重试'
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  if (accepted) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0c0e12] px-4">
        <Card className="w-full max-w-md shadow-2xl" variant="borderless">
          <div className="text-center mb-6">
            <div className="flex justify-center mb-4">
              <Brand size="lg" />
            </div>
            <CheckCircleFilled className="text-3xl text-[#4ade80] mb-3" />
            <Typography.Title level={4} className="!mb-2">
              注册申请已提交
            </Typography.Title>
            <Typography.Paragraph type="secondary" className="!text-sm">
              您的申请已进入待审批状态，管理员审批通过后即可使用该账号登录，
              审批结果以登录时的提示为准。
            </Typography.Paragraph>
          </div>
          <Link to="/login">
            <Button type="primary" size="large" block>
              返回登录
            </Button>
          </Link>
        </Card>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0c0e12] px-4">
      <Card className="w-full max-w-md shadow-2xl" variant="borderless">
        <div className="text-center mb-8">
          <div className="flex justify-center mb-4">
            <Brand size="lg" />
          </div>
          <Typography.Text type="secondary">申请创建新账户</Typography.Text>
        </div>

        {error && (
          <Alert message={error} type="error" showIcon className="mb-6" closable onClose={() => setError(null)} />
        )}

        <Form<RegisterFormValues>
          name="register"
          layout="vertical"
          onFinish={handleSubmit}
          autoComplete="off"
        >
          <Form.Item
            label="用户名"
            name="username"
            rules={[
              { required: true, message: '请输入用户名' },
              { min: 3, message: '用户名至少 3 个字符' },
            ]}
          >
            <Input prefix={<UserOutlined />} placeholder="用户名" size="large" />
          </Form.Item>

          <Form.Item
            label="邮箱"
            name="email"
            rules={[
              { required: true, message: '请输入邮箱' },
              { type: 'email', message: '请输入有效的邮箱地址' },
            ]}
          >
            <Input prefix={<MailOutlined />} placeholder="邮箱" size="large" />
          </Form.Item>

          <Form.Item
            label="密码"
            name="password"
            rules={[
              { required: true, message: '请输入密码' },
              { min: 6, message: '密码至少 6 个字符' },
            ]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="密码" size="large" />
          </Form.Item>

          <Form.Item
            label="确认密码"
            name="confirmPassword"
            dependencies={['password']}
            rules={[
              { required: true, message: '请确认密码' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('password') === value) {
                    return Promise.resolve()
                  }
                  return Promise.reject(new Error('两次输入的密码不一致'))
                },
              }),
            ]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="确认密码" size="large" />
          </Form.Item>

          <Form.Item
            label="申请说明（可选）"
            name="applicationNote"
            rules={[{ max: 500, message: '申请说明不超过 500 字' }]}
          >
            <Input.TextArea
              placeholder="简单介绍自己与用途，帮助管理员审批"
              rows={3}
              showCount
              maxLength={500}
            />
          </Form.Item>

          <Form.Item>
            <Button type="primary" htmlType="submit" size="large" block disabled={loading}>
              {loading ? <Spin size="small" /> : '提交申请'}
            </Button>
          </Form.Item>
        </Form>

        <div className="text-center">
          <Typography.Text type="secondary">
            已有账户？<Link to="/login" className="ml-1">立即登录</Link>
          </Typography.Text>
        </div>
      </Card>
    </div>
  )
}
