import { LockOutlined, UserOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Form, Input, Spin, Typography } from 'antd'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { login } from '@/api/auth'
import { Brand } from '@/components/common/Brand'
import { useAuthStore } from '@/stores/auth'

interface LoginFormValues {
  username: string
  password: string
}

export function Login() {
  const navigate = useNavigate()
  const authLogin = useAuthStore((state) => state.login)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (values: LoginFormValues) => {
    setLoading(true)
    setError(null)
    try {
      const result = await login(values)
      authLogin(result.accessToken, result.user)
      navigate('/')
    } catch (err) {
      const message = err instanceof Error ? err.message : '登录失败，请重试'
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
          <Typography.Text type="secondary">登录您的账户</Typography.Text>
        </div>

        {error && (
          <Alert message={error} type="error" showIcon className="mb-6" closable onClose={() => setError(null)} />
        )}

        <Form<LoginFormValues>
          name="login"
          layout="vertical"
          onFinish={handleSubmit}
          autoComplete="off"
        >
          <Form.Item
            label="用户名"
            name="username"
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input prefix={<UserOutlined />} placeholder="用户名" size="large" />
          </Form.Item>

          <Form.Item
            label="密码"
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="密码" size="large" />
          </Form.Item>

          <Form.Item>
            <Button type="primary" htmlType="submit" size="large" block disabled={loading}>
              {loading ? <Spin size="small" /> : '登录'}
            </Button>
          </Form.Item>
        </Form>

        <div className="text-center">
          <Typography.Text type="secondary">
            还没有账户？<Link to="/register" className="ml-1">立即注册</Link>
          </Typography.Text>
        </div>
      </Card>
    </div>
  )
}
