import { LockOutlined, MailOutlined, UserOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Form, Input, Spin, Typography } from 'antd'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { register } from '@/api/auth'
import { Brand } from '@/components/common/Brand'
import { useAuthStore } from '@/stores/auth'

interface RegisterFormValues {
  username: string
  email: string
  password: string
  confirmPassword: string
}

export function Register() {
  const navigate = useNavigate()
  const authLogin = useAuthStore((state) => state.login)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (values: RegisterFormValues) => {
    setLoading(true)
    setError(null)
    try {
      const result = await register({
        username: values.username,
        email: values.email,
        password: values.password,
      })
      authLogin(result.accessToken, result.user)
      navigate('/')
    } catch (err) {
      const message = err instanceof Error ? err.message : '注册失败，请重试'
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0c0e12] px-4">
      <Card className="w-full max-w-md shadow-2xl" variant="borderless">
        <div className="text-center mb-8">
          <div className="flex justify-center mb-4">
            <Brand size="lg" />
          </div>
          <Typography.Text type="secondary">创建新账户</Typography.Text>
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

          <Form.Item>
            <Button type="primary" htmlType="submit" size="large" block disabled={loading}>
              {loading ? <Spin size="small" /> : '注册'}
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
