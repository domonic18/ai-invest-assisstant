import { EyeOutlined, RobotOutlined } from '@ant-design/icons'
import {
  Alert,
  Button,
  Card,
  DatePicker,
  Descriptions,
  Drawer,
  Popconfirm,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
  message,
} from 'antd'
import dayjs, { type Dayjs } from 'dayjs'
import { useEffect, useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import type { AdminAiResultItem } from '@ai-invest/shared'

import {
  invalidateAiResultCaches,
  useAdminAiResultDetail,
  useAdminAiResults,
  useAiResultSkills,
  useDeleteAdminAiResult,
} from '@/hooks/useAdminAiResults'
import { usePageAssistantResultAny } from '@/hooks/usePageAssistantResult'
import { useAssistantStore, type PageAssistantResult } from '@/stores/assistant'
import { formatDateTime } from '@/utils/formatters'

import { JsonView } from './JsonView'

const STATUS_OPTIONS = [
  { value: 'success', label: '成功' },
  { value: 'failed', label: '失败' },
]

const STATUS_TAG_COLOR: Record<string, string> = {
  success: 'green',
  failed: 'red',
}

function formatLatency(latencyMs: number | null): string {
  if (latencyMs == null || latencyMs === 0) return '-'
  return `${(latencyMs / 1000).toFixed(1)}s`
}

function keyFieldsText(record: AdminAiResultItem): string {
  return record.keyFields.map((field) => field.value).join(' · ')
}

export function AiResultsAdmin() {
  const [activeSkill, setActiveSkill] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [dateRange, setDateRange] = useState<[string | null, string | null]>([null, null])
  const [status, setStatus] = useState<string | undefined>(undefined)
  const [detailId, setDetailId] = useState<number | null>(null)
  const [generatingId, setGeneratingId] = useState<number | null>(null)

  const skillsQuery = useAiResultSkills()
  const skills = useMemo(() => skillsQuery.data ?? [], [skillsQuery.data])
  const listQuery = useAdminAiResults(
    {
      skillId: activeSkill ?? '',
      status,
      startDate: dateRange[0] ?? undefined,
      endDate: dateRange[1] ?? undefined,
      page,
      pageSize,
    },
    activeSkill !== null,
  )
  const detailQuery = useAdminAiResultDetail(detailId)
  const deleteMutation = useDeleteAdminAiResult()

  const queryClient = useQueryClient()
  const panelOpen = useAssistantStore((s) => s.open)

  useEffect(() => {
    if (activeSkill === null && skills.length > 0) setActiveSkill(skills[0].skillId)
  }, [activeSkill, skills])

  // 完成事件按后端注册表的 event_type 订阅：新增 skill 纳管后无需改此页面
  const eventTypes = useMemo(
    () =>
      skills
        .map((s) => s.eventType)
        .filter((t): t is PageAssistantResult['type'] => t !== null),
    [skills],
  )
  const skillIdByEvent = useMemo(() => {
    const map: Partial<Record<PageAssistantResult['type'], string>> = {}
    for (const skill of skills) {
      if (skill.eventType !== null) {
        // 后端注册表的 event_type 与前端 PageAssistantResult 联合保持一致
        map[skill.eventType as PageAssistantResult['type']] = skill.skillId
      }
    }
    return map
  }, [skills])

  usePageAssistantResultAny(eventTypes, (result) => {
    if (generatingId === null) return false
    setGeneratingId(null)
    invalidateAiResultCaches(queryClient, skillIdByEvent[result.type])
    message.success('AI 生成完成，列表已刷新')
    return true
  })

  // 侧边栏关闭（含 agent 中途失败被放弃）时解除进行中提示
  useEffect(() => {
    if (!panelOpen) setGeneratingId(null)
  }, [panelOpen])

  const handleRegenerate = (record: AdminAiResultItem) => {
    if (!record.regeneratePrompt) return
    setGeneratingId(record.id)
    useAssistantStore.getState().sendQuestion(record.regeneratePrompt)
  }

  const handleDelete = async (record: AdminAiResultItem) => {
    try {
      await deleteMutation.mutateAsync({ id: record.id, skillId: record.skillId })
      message.success('已删除该记录的全部生成历史')
    } catch (err) {
      message.error(err instanceof Error && err.message ? err.message : '删除失败')
    }
  }

  const handleRangeChange = (dates: [Dayjs | null, Dayjs | null] | null) => {
    setDateRange(
      dates
        ? [dates[0]?.format('YYYY-MM-DD') ?? null, dates[1]?.format('YYYY-MM-DD') ?? null]
        : [null, null],
    )
    setPage(1)
  }

  const columns = [
    {
      title: '业务键',
      key: 'keyFields',
      render: (_: unknown, record: AdminAiResultItem) => keyFieldsText(record) || '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (value: string) => (
        <Tag color={STATUS_TAG_COLOR[value] ?? 'default'}>{value}</Tag>
      ),
    },
    {
      title: '模型',
      dataIndex: 'model',
      key: 'model',
      width: 150,
      render: (value: string | null) =>
        value ? <Tag color="blue">{value}</Tag> : '-',
    },
    {
      title: '生成耗时',
      dataIndex: 'latencyMs',
      key: 'latencyMs',
      width: 100,
      render: (value: number | null) => formatLatency(value),
    },
    {
      title: '生成时间',
      dataIndex: 'createdAt',
      key: 'createdAt',
      width: 180,
      render: (value: string) => formatDateTime(value),
    },
    {
      title: '生成记录数',
      dataIndex: 'historyCount',
      key: 'historyCount',
      width: 110,
      render: (value: number) => (value > 1 ? <Tag color="orange">{value} 条</Tag> : '1 条'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 280,
      render: (_: unknown, record: AdminAiResultItem) => (
        <Space>
          <Button size="small" icon={<EyeOutlined />} onClick={() => setDetailId(record.id)}>
            查看
          </Button>
          {record.regeneratePrompt && (
            <Button
              size="small"
              icon={<RobotOutlined />}
              loading={generatingId === record.id}
              disabled={generatingId !== null && generatingId !== record.id}
              onClick={() => handleRegenerate(record)}
            >
              AI 重新生成
            </Button>
          )}
          <Popconfirm
            title={`删除该记录及同键全部 ${record.historyCount} 条生成记录？`}
            description="删除后可重新生成；用户编辑副本与产业链版本内容不受影响"
            onConfirm={() => handleDelete(record)}
          >
            <Button size="small" danger loading={deleteMutation.isPending}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  const detail = detailQuery.data

  return (
    <Card title="AI 结果管理" variant="borderless">
      <Tabs
        activeKey={activeSkill ?? undefined}
        items={skills.map((skill) => ({ key: skill.skillId, label: skill.label }))}
        onChange={(key) => {
          setActiveSkill(key)
          setPage(1)
        }}
      />
      <Space className="mb-4" wrap>
        <DatePicker.RangePicker
          value={
            dateRange[0] && dateRange[1]
              ? ([dayjs(dateRange[0]), dayjs(dateRange[1])] as [Dayjs, Dayjs])
              : null
          }
          onChange={handleRangeChange}
          allowEmpty={[true, true]}
        />
        <Select
          value={status}
          options={STATUS_OPTIONS}
          allowClear
          placeholder="全部状态"
          style={{ width: 120 }}
          onChange={(value) => {
            setStatus(value)
            setPage(1)
          }}
        />
      </Space>
      {listQuery.error && (
        <Alert
          message="加载失败"
          description={listQuery.error instanceof Error ? listQuery.error.message : '未知错误'}
          type="error"
          showIcon
          className="mb-4"
        />
      )}
      <Typography.Paragraph type="secondary" className="!mb-3">
        每个业务键显示最新一条生成记录；删除会清空该键全部生成历史（缓存清除语义），可重新生成。
      </Typography.Paragraph>
      <Table
        dataSource={listQuery.data?.items ?? []}
        columns={columns}
        rowKey="id"
        loading={listQuery.isLoading}
        scroll={{ x: 'max-content' }}
        pagination={{
          current: page,
          pageSize,
          total: listQuery.data?.total ?? 0,
          showSizeChanger: true,
          showTotal: (total) => `共 ${total} 条记录`,
          onChange: (p, ps) => {
            setPage(p)
            setPageSize(ps)
          },
        }}
      />
      <Drawer
        title="生成记录详情"
        width={560}
        open={detailId !== null}
        onClose={() => setDetailId(null)}
        destroyOnClose
      >
        {detail && (
          <>
            <Descriptions
              size="small"
              column={1}
              bordered
              items={[
                {
                  key: 'keyFields',
                  label: '业务键',
                  children: detail.keyFields.map((f) => `${f.label}: ${f.value}`).join('，'),
                },
                { key: 'status', label: '状态', children: detail.status },
                { key: 'model', label: '模型', children: detail.model ?? '-' },
                { key: 'latencyMs', label: '生成耗时', children: formatLatency(detail.latencyMs) },
                { key: 'createdAt', label: '生成时间', children: formatDateTime(detail.createdAt) },
                { key: 'historyCount', label: '生成记录数', children: `${detail.historyCount} 条` },
              ]}
            />
            {detail.errorMsg && (
              <Alert
                message="生成失败"
                description={detail.errorMsg}
                type="error"
                showIcon
                className="mt-4"
              />
            )}
            <Typography.Paragraph type="secondary" className="!mt-4 !mb-2">
              结构化输出
            </Typography.Paragraph>
            <JsonView data={detail.structuredOutput ?? {}} />
          </>
        )}
      </Drawer>
    </Card>
  )
}
