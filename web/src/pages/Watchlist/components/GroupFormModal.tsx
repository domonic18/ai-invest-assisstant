import { useEffect } from 'react'
import { Form, Input, message, Modal } from 'antd'
import type { WatchlistGroup } from '@ai-invest/shared'

import { useCreateWatchlistGroup, useUpdateWatchlistGroup } from '@/hooks/useWatchlistGroups'

import { apiErrorMessage } from '@/utils/errorMessage'

interface GroupFormModalProps {
  open: boolean
  /** null 表示新建，否则为编辑该分组。 */
  group: WatchlistGroup | null
  onClose: () => void
}

interface FormValues {
  name: string
}

export function GroupFormModal({ open, group, onClose }: GroupFormModalProps) {
  const [form] = Form.useForm<FormValues>()
  const createMutation = useCreateWatchlistGroup()
  const updateMutation = useUpdateWatchlistGroup()
  const editing = group !== null

  useEffect(() => {
    if (open) {
      form.setFieldsValue({ name: group?.name ?? '' })
    }
  }, [open, group, form])

  const close = () => {
    form.resetFields()
    onClose()
  }

  const submit = async (values: FormValues) => {
    const name = values.name.trim()
    try {
      if (editing) {
        await updateMutation.mutateAsync({ groupId: group.id, data: { name } })
        message.success('分组已更新')
      } else {
        await createMutation.mutateAsync({ name })
        message.success('分组已创建')
      }
      close()
    } catch (err) {
      message.error(apiErrorMessage(err, editing ? '分组更新失败' : '分组创建失败'))
    }
  }

  return (
    <Modal
      title={editing ? '编辑分组' : '新建分组'}
      open={open}
      onCancel={close}
      onOk={() => form.submit()}
      okText={editing ? '保存' : '创建'}
      confirmLoading={createMutation.isPending || updateMutation.isPending}
    >
      <Form form={form} layout="vertical" onFinish={submit}>
        <Form.Item
          name="name"
          label="分组名称"
          rules={[
            { required: true, whitespace: true, message: '请输入分组名称' },
            { max: 50, message: '名称不超过 50 个字符' },
          ]}
        >
          <Input placeholder="如：科技 / 新能源" maxLength={50} />
        </Form.Item>
      </Form>
    </Modal>
  )
}
