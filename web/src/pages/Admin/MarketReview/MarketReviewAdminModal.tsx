import { useQuery } from '@tanstack/react-query'
import { Alert, DatePicker, Form, Input, Modal, Radio, Spin, message } from 'antd'
import dayjs, { type Dayjs } from 'dayjs'
import { useEffect, useState } from 'react'

import {
  fetchAdminMarketReviewDetail,
  fetchMarketReviewSectionDefinitions,
} from '@/api/adminMarketReviews'
import {
  useCreateAdminMarketReview,
  useUpdateAdminMarketReview,
} from '@/hooks/useAdminMarketReviews'

interface MarketReviewAdminModalProps {
  open: boolean
  /** null = 新增模式；非空 = 编辑该交易日的最新记录 */
  tradeDate: string | null
  onCancel: () => void
  /** 创建模式选择「AI 生成」时：唤起侧边栏 agent 生成指定交易日复盘 */
  onAIAsk?: (tradeDate: string) => void
}

type CreateMode = 'manual' | 'ai'

const errorMessage = (err: unknown, fallback: string) =>
  err instanceof Error && err.message ? err.message : fallback

export function MarketReviewAdminModal({
  open,
  tradeDate,
  onCancel,
  onAIAsk,
}: MarketReviewAdminModalProps) {
  const isEdit = tradeDate !== null
  const [form] = Form.useForm<{ tradeDate?: Dayjs; createMode?: CreateMode }>()
  const [createMode, setCreateMode] = useState<CreateMode>('ai')
  const [sections, setSections] = useState<Record<string, string>>({})

  const definitionsQuery = useQuery({
    queryKey: ['admin-market-review-section-defs'],
    queryFn: fetchMarketReviewSectionDefinitions,
    enabled: open && !isEdit,
  })
  const detailQuery = useQuery({
    queryKey: ['admin-market-review-detail', tradeDate],
    queryFn: () => fetchAdminMarketReviewDetail(tradeDate as string),
    enabled: open && isEdit,
  })

  useEffect(() => {
    if (!open) return
    form.resetFields()
    setCreateMode('ai')
    setSections({})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, tradeDate])

  useEffect(() => {
    if (!open || !isEdit || !detailQuery.data) return
    const filled: Record<string, string> = {}
    for (const section of detailQuery.data.sections) filled[section.key] = section.content
    setSections(filled)
  }, [open, isEdit, detailQuery.data])

  const createMutation = useCreateAdminMarketReview()
  const updateMutation = useUpdateAdminMarketReview()
  const submitting = createMutation.isPending || updateMutation.isPending

  const handleOk = async () => {
    if (isEdit) {
      try {
        await updateMutation.mutateAsync({ tradeDate, sections })
        message.success('复盘内容已更新（生成一条新记录）')
        onCancel()
      } catch (err) {
        message.error(errorMessage(err, '保存失败'))
      }
      return
    }

    const values = await form.validateFields()
    const targetDate = values.tradeDate?.format('YYYY-MM-DD')
    if (!targetDate) return
    if (values.createMode === 'ai') {
      onAIAsk?.(targetDate)
      onCancel()
      return
    }
    try {
      await createMutation.mutateAsync({ tradeDate: targetDate, sections })
      message.success('手动复盘已创建')
      onCancel()
    } catch (err) {
      message.error(errorMessage(err, '创建失败'))
    }
  }

  const manualFields = isEdit
    ? (detailQuery.data?.sections ?? [])
    : (definitionsQuery.data ?? [])
  const showManualFields = isEdit || createMode === 'manual'

  return (
    <Modal
      title={isEdit ? `编辑复盘 - ${tradeDate}` : '新增复盘'}
      open={open}
      onOk={handleOk}
      onCancel={onCancel}
      confirmLoading={submitting}
      okText={isEdit ? '保存' : createMode === 'ai' ? 'AI 生成' : '创建'}
      width={720}
      destroyOnClose
    >
      <Spin spinning={isEdit && detailQuery.isLoading}>
        {!isEdit && (
          <Form form={form} layout="vertical" initialValues={{ createMode: 'ai' }}>
            <Form.Item
              label="交易日"
              name="tradeDate"
              rules={[{ required: true, message: '请选择交易日' }]}
            >
              <DatePicker
                style={{ width: 200 }}
                disabledDate={(d) => d.isAfter(dayjs(), 'day')}
              />
            </Form.Item>
            <Form.Item label="生成方式" name="createMode">
              <Radio.Group
                onChange={(e) => setCreateMode(e.target.value)}
                options={[
                  { value: 'ai', label: 'AI 生成（侧边栏助手执行）' },
                  { value: 'manual', label: '手动填写' },
                ]}
              />
            </Form.Item>
          </Form>
        )}

        {showManualFields && (
          <>
            {(isEdit ? detailQuery.error : definitionsQuery.error) && (
              <Alert
                type="error"
                showIcon
                className="mb-4"
                message="分区定义/内容加载失败"
              />
            )}
            {manualFields.map((section) => (
              <Form.Item
                key={section.key}
                label={section.title}
                required
                validateStatus={!(sections[section.key] ?? '').trim() ? 'error' : undefined}
                help={!(sections[section.key] ?? '').trim() ? '内容不能为空' : undefined}
              >
                <Input.TextArea
                  rows={5}
                  value={sections[section.key] ?? ''}
                  onChange={(e) =>
                    setSections((prev) => ({ ...prev, [section.key]: e.target.value }))
                  }
                />
              </Form.Item>
            ))}
          </>
        )}
      </Spin>
    </Modal>
  )
}
