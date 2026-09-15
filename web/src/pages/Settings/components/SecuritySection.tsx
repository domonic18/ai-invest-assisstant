/** 账号安全 section：修改密码表单 + 退出登录危险操作卡。 */

import { LogoutOutlined } from '@ant-design/icons'
import { App, Button, Card, Form, Input } from 'antd'
import { useNavigate } from 'react-router-dom'

import { useChangeMyPassword } from '@/hooks/useUsers'
import { useAuthStore } from '@/stores/auth'
import { HintBox } from './SettingHints'

interface PasswordFormValues {
  currentPassword: string
  newPassword: string
  confirmPassword: string
}

export function SecuritySection() {
  const navigate = useNavigate()
  const { message } = App.useApp()
  const { logout } = useAuthStore()
  const changePassword = useChangeMyPassword()
  const [pwdForm] = Form.useForm<PasswordFormValues>()

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

  return (
    <>
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
    </>
  )
}
