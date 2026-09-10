import { InboxOutlined } from '@ant-design/icons'
import { Alert, App, Button, Drawer, Form, Input, Upload } from 'antd'
import { useEffect, useState } from 'react'

import { fetchSkillDetail } from '@/api/skills'
import {
  useAnalyzeSkillArchive,
  useCreateCustomSkill,
  useUpdateCustomSkill,
} from '@/hooks/useSkills'
import { SKILL_MD_PLACEHOLDER, USER_PROMPT_TEMPLATE_HINT } from '../constants'

interface SkillFormValues {
  skillId: string
  label: string
  description?: string
  skillMd: string
  systemPrompt: string
  userPromptTemplate?: string
}

interface SkillFormDrawerProps {
  target: { skillId: string } | 'new' | null
  onClose: () => void
}

/** 创建 / 编辑自定义技能共用抽屉：编辑时 skillId 只读，保存后版本 +1。 */
export function SkillFormDrawer({ target, onClose }: SkillFormDrawerProps) {
  const { message } = App.useApp()
  const [form] = Form.useForm<SkillFormValues>()
  const createSkill = useCreateCustomSkill()
  const updateSkill = useUpdateCustomSkill()
  const analyzeArchive = useAnalyzeSkillArchive()
  const [analyzed, setAnalyzed] = useState(false)
  const isEditing = target != null && target !== 'new'
  const editingSkillId = isEditing ? (target as { skillId: string }).skillId : null

  useEffect(() => {
    if (target == null) return
    if (target === 'new') {
      form.resetFields()
      setAnalyzed(false)
      return
    }
    // 编辑态：customDefinition 全文需从详情读取，列表项不带
    let cancelled = false
    void (async () => {
      try {
        const detail = await fetchSkillDetail(target.skillId)
        if (cancelled) return
        form.setFieldsValue({
          skillId: detail.skillId,
          label: detail.label,
          description: detail.description ?? undefined,
          skillMd: detail.customDefinition?.skillMd ?? '',
          systemPrompt: detail.customDefinition?.systemPrompt ?? '',
          userPromptTemplate: detail.customDefinition?.userPromptTemplate ?? undefined,
        })
      } catch (error) {
        if (!cancelled) {
          message.error(error instanceof Error ? error.message : '读取技能详情失败')
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [target, form, message])

  const handleSave = async (values: SkillFormValues) => {
    const customDefinition = {
      skillMd: values.skillMd,
      systemPrompt: values.systemPrompt,
      userPromptTemplate: values.userPromptTemplate ?? null,
    }
    try {
      if (editingSkillId != null) {
        await updateSkill.mutateAsync({
          skillId: editingSkillId,
          payload: {
            label: values.label,
            description: values.description ?? null,
            customDefinition,
          },
        })
      } else {
        await createSkill.mutateAsync({
          skillId: values.skillId,
          label: values.label,
          description: values.description ?? null,
          customDefinition,
        })
      }
      onClose()
    } catch {
      // 错误提示由 hooks onError 统一处理
    }
  }

  const handleArchiveUpload = async (file: File) => {
    try {
      const suggestion = await analyzeArchive.mutateAsync(file)
      form.setFieldsValue({
        skillId: suggestion.skillId,
        label: suggestion.label,
        description: suggestion.description ?? undefined,
        skillMd: suggestion.skillMd,
        systemPrompt: suggestion.systemPrompt,
        userPromptTemplate: suggestion.userPromptTemplate ?? undefined,
      })
      setAnalyzed(true)
      message.success('已从压缩包自动解析技能内容')
    } catch {
      // 错误提示由 hooks onError 统一处理
    }
    return false
  }

  return (
    <Drawer
      title={isEditing ? '编辑自定义技能' : '创建自定义技能'}
      placement="right"
      width={520}
      open={target != null}
      onClose={onClose}
      destroyOnClose
    >
      <Form form={form} layout="vertical" onFinish={handleSave}>
        {!isEditing && (
          <>
            <Upload.Dragger
              accept=".zip,.tar.gz,.tgz"
              showUploadList={false}
              beforeUpload={(file) => {
                void handleArchiveUpload(file)
                return false
              }}
              disabled={analyzeArchive.isPending}
              className="!mb-4"
            >
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text !text-sm">
                {analyzeArchive.isPending ? '解析中…' : '上传技能压缩包自动填写'}
              </p>
              <p className="ant-upload-hint !text-xs">
                拖入 .zip / .tar.gz（须含 SKILL.md），解析后可在下方修改
              </p>
            </Upload.Dragger>
            {analyzed && (
              <Alert
                type="success"
                showIcon
                message="已从压缩包自动解析"
                description="以下字段为解析建议，可继续手动调整后保存。"
                className="!mb-4"
              />
            )}
          </>
        )}
        <Form.Item
          name="skillId"
          label="skill_id"
          rules={[
            { required: true, message: '请输入技能 ID' },
            { pattern: /^[a-z][a-z0-9-]*$/, message: '小写字母开头，仅含小写字母、数字与连字符' },
          ]}
          extra="全局唯一；不可与内置技能或他人自定义技能重名"
        >
          <Input placeholder="dragon-head-review" disabled={isEditing} />
        </Form.Item>
        <Form.Item name="label" label="名称" rules={[{ required: true, message: '请输入名称' }]}>
          <Input placeholder="龙头战法每日复盘" />
        </Form.Item>
        <Form.Item name="description" label="描述">
          <Input.TextArea rows={2} placeholder="一句话说明技能用途，将展示在广场卡片与助手技能索引中" />
        </Form.Item>
        <Form.Item
          name="skillMd"
          label="SKILL.md"
          rules={[{ required: true, message: '请输入 SKILL.md 内容' }]}
        >
          <Input.TextArea rows={8} placeholder={SKILL_MD_PLACEHOLDER} className="font-mono !text-xs" />
        </Form.Item>
        <Form.Item
          name="systemPrompt"
          label="System Prompt"
          rules={[{ required: true, message: '请输入 System Prompt' }]}
        >
          <Input.TextArea rows={6} placeholder="你是一名专注 A 股龙头股战法的分析师…" className="font-mono !text-xs" />
        </Form.Item>
        <Form.Item name="userPromptTemplate" label="User Prompt 模板" extra={USER_PROMPT_TEMPLATE_HINT}>
          <Input.TextArea rows={4} placeholder="请复盘 {trade_date} 的龙头股…" className="font-mono !text-xs" />
        </Form.Item>
        <div className="flex justify-end gap-2 pt-2">
          <Button onClick={onClose}>取消</Button>
          <Button
            type="primary"
            htmlType="submit"
            loading={createSkill.isPending || updateSkill.isPending}
          >
            保存{isEditing ? '（版本 +1）' : '为草稿'}
          </Button>
        </div>
      </Form>
    </Drawer>
  )
}
