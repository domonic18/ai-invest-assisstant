import {
  Alert,
  Button,
  Card,
  Collapse,
  Descriptions,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import { useMemo, useState } from 'react'

import type {
  ApiKbOptimizationSuggestion,
  ApiKbOptimizationSuggestionItem,
} from '@ai-invest/shared'

import {
  useCreateKbOptimizationSuggestion,
  useKbOptimizationSuggestions,
  useKbSources,
  useReviewKbOptimizationSuggestion,
} from '@/hooks/useAdminKb'
import { useSkillSquare } from '@/hooks/useSkills'

const STATUS_META: Record<string, { label: string; color: string }> = {
  queued: { label: '排队中', color: 'blue' },
  generating: { label: '生成中', color: 'processing' },
  pending_review: { label: '待审核', color: 'orange' },
  applied: { label: '已应用', color: 'green' },
  rejected: { label: '已驳回', color: 'default' },
  failed: { label: '失败', color: 'red' },
}

const STATUS_OPTIONS = Object.entries(STATUS_META).map(([value, meta]) => ({
  value,
  label: meta.label,
}))

const PAGE_SIZE = 10

interface TriggerFormValues {
  skillId: string
  sourceId: number
}

interface SuggestionBlockProps {
  item: ApiKbOptimizationSuggestionItem
  index: number
  editedText: string | null
  onEdit: (index: number, text: string) => void
  reviewable: boolean
}

function SuggestionBlock({ item, index, editedText, onEdit, reviewable }: SuggestionBlockProps) {
  const showRevised = editedText != null && editedText !== item.suggestedText
  return (
    <Card size="small" style={{ marginBottom: 12 }} title={`#${index + 1} ${item.targetFile} · ${item.section}`}>
      {item.originalText ? (
        <Typography.Paragraph>
          <Typography.Text type="secondary">原文：</Typography.Text>
          <Typography.Text delete>{item.originalText}</Typography.Text>
        </Typography.Paragraph>
      ) : (
        <Typography.Paragraph type="secondary">（新增类建议，无原文）</Typography.Paragraph>
      )}
      {reviewable ? (
        <Typography.Paragraph>
          <Typography.Text type="secondary">建议文本（可修订后应用）：</Typography.Text>
          <Input.TextArea
            rows={3}
            value={editedText ?? item.suggestedText}
            onChange={(e) => onEdit(index, e.target.value)}
          />
        </Typography.Paragraph>
      ) : (
        <Typography.Paragraph>
          <Typography.Text type="secondary">建议文本：</Typography.Text>
          {showRevised ? (
            <>
              <Typography.Text delete>{item.suggestedText}</Typography.Text>{' '}
              <Typography.Text>{editedText}</Typography.Text>
            </>
          ) : (
            item.suggestedText
          )}
        </Typography.Paragraph>
      )}
      <Typography.Paragraph type="secondary" style={{ marginBottom: 4 }}>
        理由：{item.reason}
      </Typography.Paragraph>
      {item.citations.length > 0 && (
        <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
          引用：{item.citations.join('；')}
        </Typography.Paragraph>
      )}
    </Card>
  )
}

export function OptimizationTab() {
  const [statusFilter, setStatusFilter] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [editedTexts, setEditedTexts] = useState<Record<string, string>>({})
  const [rejectTarget, setRejectTarget] = useState<ApiKbOptimizationSuggestion | null>(null)
  const [rejectNote, setRejectNote] = useState('')
  const [applyTarget, setApplyTarget] = useState<ApiKbOptimizationSuggestion | null>(null)
  const [form] = Form.useForm<TriggerFormValues>()

  const { data: square } = useSkillSquare()
  const { data: sources } = useKbSources()
  const { data, isLoading } = useKbOptimizationSuggestions(statusFilter, page, PAGE_SIZE)
  const createMutation = useCreateKbOptimizationSuggestion()
  const reviewMutation = useReviewKbOptimizationSuggestion()

  const skillOptions = useMemo(() => {
    const seen = new Set<string>()
    const options: { value: string; label: string }[] = []
    for (const item of [...(square?.mine ?? []), ...(square?.available ?? [])]) {
      if (seen.has(item.skillId)) continue
      seen.add(item.skillId)
      options.push({
        value: item.skillId,
        label: `${item.label}（${item.isBuiltin ? 'builtin' : 'custom'} · ${item.skillId}）`,
      })
    }
    return options
  }, [square])

  const sourceOptions = (sources ?? [])
    .filter((s) => s.enabled)
    .map((s) => ({ value: s.id, label: s.name }))

  const handleTrigger = async (values: TriggerFormValues) => {
    await createMutation.mutateAsync(values)
    message.success('建议单已创建，生成任务已派发（生成约需数分钟）')
    form.resetFields()
    setPage(1)
    setStatusFilter(null)
  }

  const handleApply = (row: ApiKbOptimizationSuggestion) => {
    setApplyTarget(null)
    const suggestions = row.suggestions ?? []
    const revisions = suggestions
      .map((item, index) => {
        const text = editedTexts[`${row.id}-${index}`]
        return text && text !== item.suggestedText
          ? { index, suggestedText: text }
          : null
      })
      .filter((r): r is { index: number; suggestedText: string } => r != null)
    reviewMutation.mutate(
      {
        id: row.id,
        data: {
          action: 'apply',
          revisions: revisions.length > 0 ? revisions : undefined,
        },
      },
      {
        onSuccess: () => {
          message.success(
            row.skillKind === 'custom'
              ? '已应用：技能定义已更新（version+1）'
              : '已应用：应用后全文已导出留档，交开发核对落库'
          )
          setEditedTexts({})
        },
      }
    )
  }

  const handleReject = () => {
    if (!rejectTarget) return
    if (!rejectNote.trim()) {
      message.warning('请填写驳回理由')
      return
    }
    reviewMutation.mutate(
      { id: rejectTarget.id, data: { action: 'reject', note: rejectNote } },
      {
        onSuccess: () => {
          message.success('已驳回')
          setRejectTarget(null)
          setRejectNote('')
        },
      }
    )
  }

  const columns = [
    { title: '技能', dataIndex: 'skillLabel', key: 'skillLabel', render: (_: unknown, row: ApiKbOptimizationSuggestion) => (
      <Space direction="vertical" size={0}>
        <span>{row.skillLabel}</span>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          {row.skillId} · {row.skillKind === 'builtin' ? 'builtin' : 'custom'} v{row.skillVersion}
        </Typography.Text>
      </Space>
    ) },
    { title: '知识源', dataIndex: 'sourceName', key: 'sourceName' },
    { title: '状态', dataIndex: 'status', key: 'status', render: (status: string) => (
      <Tag color={STATUS_META[status]?.color}>{STATUS_META[status]?.label ?? status}</Tag>
    ) },
    { title: '模型', dataIndex: 'modelName', key: 'modelName', render: (v: string | null) => v ?? '-' },
    { title: '修改点', key: 'count', render: (_: unknown, row: ApiKbOptimizationSuggestion) =>
      row.suggestions ? row.suggestions.length : '-'
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, row: ApiKbOptimizationSuggestion) => (
        <Space>
          {row.status === 'pending_review' && (
            <>
              <Button
                size="small"
                type="primary"
                loading={reviewMutation.isPending}
                onClick={() => setApplyTarget(row)}
              >
                应用
              </Button>
              <Button size="small" danger onClick={() => setRejectTarget(row)}>
                驳回
              </Button>
            </>
          )}
          {row.status === 'failed' && row.error && (
            <Typography.Text type="danger" style={{ fontSize: 12 }}>
              {row.error}
            </Typography.Text>
          )}
        </Space>
      ),
    },
  ]

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={16}>
      <Card size="small" title="发起优化建议（目标技能 × 知识源）">
        <Form form={form} layout="inline" onFinish={handleTrigger}>
          <Form.Item
            name="skillId"
            rules={[{ required: true, message: '选择目标技能' }]}
            style={{ minWidth: 280 }}
          >
            <Select placeholder="目标技能" options={skillOptions} showSearch optionFilterProp="label" />
          </Form.Item>
          <Form.Item
            name="sourceId"
            rules={[{ required: true, message: '选择知识源' }]}
            style={{ minWidth: 200 }}
          >
            <Select placeholder="知识源" options={sourceOptions} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={createMutation.isPending}>
              生成建议
            </Button>
          </Form.Item>
        </Form>
        <Typography.Paragraph type="secondary" style={{ marginBottom: 0, marginTop: 8 }}>
          同一技能存在未处理建议单（排队/生成中/待审核）时不能发起新一轮；生成走后台
          Agent 检索知识源产出修改点列表，完成后进入待审核。
        </Typography.Paragraph>
      </Card>

      <Card size="small" title="建议单队列">
        <Space style={{ marginBottom: 12 }}>
          <Select
            allowClear
            placeholder="状态过滤"
            options={STATUS_OPTIONS}
            value={statusFilter}
            onChange={(v) => {
              setStatusFilter(v ?? null)
              setPage(1)
            }}
            style={{ width: 140 }}
          />
        </Space>
        <Table
          rowKey="id"
          size="small"
          loading={isLoading}
          columns={columns}
          dataSource={data?.items ?? []}
          pagination={{
            current: page,
            pageSize: PAGE_SIZE,
            total: data?.total ?? 0,
            showSizeChanger: false,
            onChange: setPage,
          }}
          expandable={{
            expandedRowRender: (row: ApiKbOptimizationSuggestion) => {
              const reviewable = row.status === 'pending_review'
              const builtinApplied =
                row.status === 'applied' &&
                row.applyResult?.kind === 'builtin_export'
              return (
                <div style={{ maxWidth: 900 }}>
                  {row.summary && (
                    <Typography.Paragraph type="secondary">{row.summary}</Typography.Paragraph>
                  )}
                  {row.status === 'failed' && row.error && (
                    <Alert type="error" message={row.error} style={{ marginBottom: 12 }} />
                  )}
                  {(row.suggestions ?? []).map((item, index) => (
                    <SuggestionBlock
                      key={index}
                      item={item}
                      index={index}
                      editedText={editedTexts[`${row.id}-${index}`] ?? null}
                      onEdit={(idx, text) =>
                        setEditedTexts((prev) => ({ ...prev, [`${row.id}-${idx}`]: text }))
                      }
                      reviewable={reviewable}
                    />
                  ))}
                  {builtinApplied && (
                    <Collapse
                      items={((row.applyResult?.files as { path: string; content: string }[]) ?? []).map(
                        (f) => ({
                          key: f.path,
                          label: `应用后全文 · ${f.path}（复制交开发落库）`,
                          children: (
                            <Input.TextArea readOnly autoSize value={f.content} />
                          ),
                        })
                      )}
                    />
                  )}
                  {row.status === 'applied' && row.applyResult?.kind === 'custom_applied' && (
                    <Alert
                      type="success"
                      message={`已直写生效：技能定义更新至 v${row.applyResult.skillVersion}`}
                    />
                  )}
                  {row.reviewNote && (
                    <Descriptions size="small" column={1} style={{ marginTop: 12 }}>
                      <Descriptions.Item label="审核备注">{row.reviewNote}</Descriptions.Item>
                    </Descriptions>
                  )}
                </div>
              )
            },
          }}
        />
      </Card>

      <Modal
        title="驳回建议单"
        open={rejectTarget != null}
        okText="驳回"
        okButtonProps={{ danger: true }}
        cancelText="取消"
        onOk={handleReject}
        onCancel={() => setRejectTarget(null)}
        confirmLoading={reviewMutation.isPending}
      >
        <Input.TextArea
          rows={3}
          placeholder="驳回理由（必填，留档）"
          value={rejectNote}
          onChange={(e) => setRejectNote(e.target.value)}
        />
      </Modal>

      <Modal
        title="应用建议单"
        open={applyTarget != null}
        okText="确认应用"
        cancelText="取消"
        onOk={() => applyTarget && handleApply(applyTarget)}
        onCancel={() => setApplyTarget(null)}
        confirmLoading={reviewMutation.isPending}
      >
        {applyTarget?.skillKind === 'custom' ? (
          <Typography.Paragraph>
            将把修改点直写进技能定义并 version+1 立即生效；已修订的文本按修订版应用。
            若任一原文与当前定义不匹配，整单不生效。
          </Typography.Paragraph>
        ) : (
          <Typography.Paragraph>
            builtin 技能运行时不改文件：应用后将导出「应用后完整文件文本」留档在本单
            （apply_result），交开发核对后落库。若任一原文与当前文件不匹配，整单不生效。
          </Typography.Paragraph>
        )}
      </Modal>
    </Space>
  )
}
