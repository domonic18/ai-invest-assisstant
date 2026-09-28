import { Form, Modal, Select } from 'antd'
import { useEffect, useMemo } from 'react'

import type { LLMConfig } from '@ai-invest/shared'

interface BackupModalProps {
  config: LLMConfig | null
  configs: LLMConfig[]
  open: boolean
  onCancel: () => void
  onSubmit: (configId: number, backupConfigId: number | null) => void
  loading: boolean
}

/** 主备关系独立配置：备用是条目间关系而非条目属性，
 *  从新建/编辑表单解耦为列表行操作（新建时同用途候选为空，无从选择）。 */
export function BackupModal({
  config,
  configs,
  open,
  onCancel,
  onSubmit,
  loading,
}: BackupModalProps) {
  const [form] = Form.useForm<{ backupConfigId?: number | null }>()

  const options = useMemo(
    () =>
      configs
        .filter((c) => c.isActive && c.purpose === config?.purpose && c.id !== config?.id)
        .map((c) => ({ value: c.id, label: `${c.name}（${c.modelName}）` })),
    [configs, config],
  )

  useEffect(() => {
    if (open) form.setFieldsValue({ backupConfigId: config?.backupConfigId ?? null })
  }, [open, config, form])

  const handleOk = async () => {
    const values = await form.validateFields()
    if (config) onSubmit(config.id, values.backupConfigId ?? null)
  }

  return (
    <Modal
      title={config ? `设置「${config.name}」的备用模型` : '设置备用模型'}
      open={open}
      onOk={handleOk}
      onCancel={onCancel}
      confirmLoading={loading}
      destroyOnClose
    >
      <Form form={form} layout="vertical">
        <Form.Item
          label="备用模型"
          name="backupConfigId"
          extra="本模型限流/额度耗尽时自动切换到该备用模型，冷却结束自动切回；候选须为同用途且已启用条目"
        >
          <Select options={options} allowClear placeholder="不指定备用" />
        </Form.Item>
      </Form>
    </Modal>
  )
}
