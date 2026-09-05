import { EditOutlined, PlusOutlined, RobotOutlined } from '@ant-design/icons'
import {
  Alert,
  Button,
  Card,
  DatePicker,
  Popconfirm,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import dayjs, { type Dayjs } from 'dayjs'
import { useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import type { AdminMarketReviewItem } from '@ai-invest/shared'

import {
  useAdminMarketReviews,
  useDeleteAdminMarketReview,
} from '@/hooks/useAdminMarketReviews'
import { queryKeys } from '@/hooks/queryKeys'
import { usePageAssistantResult } from '@/hooks/usePageAssistantResult'
import { useAssistantStore } from '@/stores/assistant'
import { formatDateTime } from '@/utils/formatters'

import { MarketReviewAdminModal } from './MarketReviewAdminModal'

const MODEL_TAG_COLOR: Record<string, string> = {
  manual: 'default',
}

function formatLatency(latencyMs: number | null): string {
  if (latencyMs == null) return '-'
  if (latencyMs === 0) return '-'
  return `${(latencyMs / 1000).toFixed(1)}s`
}

export function MarketReviewAdmin() {
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [dateRange, setDateRange] = useState<[string | null, string | null]>([null, null])

  const [modalOpen, setModalOpen] = useState(false)
  const [editingDate, setEditingDate] = useState<string | null>(null)
  const [generatingDate, setGeneratingDate] = useState<string | null>(null)

  const listQuery = useAdminMarketReviews({
    startDate: dateRange[0] ?? undefined,
    endDate: dateRange[1] ?? undefined,
    page,
    pageSize,
  })
  const deleteMutation = useDeleteAdminMarketReview()

  const queryClient = useQueryClient()
  const panelOpen = useAssistantStore((s) => s.open)

  // AI 生成走侧边栏 agent（取数/分析过程全程可见，persist 工具落库）；
  // 完成事件经 pageResult 回写后刷新本列表
  const startGenerate = (tradeDate: string, regenerate: boolean) => {
    setGeneratingDate(tradeDate)
    useAssistantStore
      .getState()
      .sendQuestion(`请${regenerate ? '重新' : ''}生成 ${tradeDate} 的大盘每日复盘`)
  }

  usePageAssistantResult('market_daily_review.complete', () => {
    if (generatingDate === null) return false
    setGeneratingDate(null)
    void queryClient.invalidateQueries({ queryKey: queryKeys.admin.marketReviews })
    message.success('AI 复盘已生成，列表已刷新')
    return true
  })

  // 侧边栏关闭（含 agent 中途失败被放弃）时解除进行中提示
  useEffect(() => {
    if (!panelOpen) setGeneratingDate(null)
  }, [panelOpen])

  const openCreate = () => {
    setEditingDate(null)
    setModalOpen(true)
  }

  const openEdit = (record: AdminMarketReviewItem) => {
    setEditingDate(record.tradeDate)
    setModalOpen(true)
  }

  const handleDelete = async (record: AdminMarketReviewItem) => {
    try {
      await deleteMutation.mutateAsync(record.tradeDate)
      message.success(`已删除 ${record.tradeDate} 的全部生成记录`)
    } catch (err) {
      message.error(err instanceof Error && err.message ? err.message : '删除失败')
    }
  }

  const handleRegenerate = (record: AdminMarketReviewItem) => {
    startGenerate(record.tradeDate, true)
  }

  const handleRangeChange = (dates: [Dayjs | null, Dayjs | null] | null) => {
    setDateRange(
      dates ? [dates[0]?.format('YYYY-MM-DD') ?? null, dates[1]?.format('YYYY-MM-DD') ?? null] : [null, null],
    )
    setPage(1)
  }

  const columns = [
    { title: '交易日', dataIndex: 'tradeDate', key: 'tradeDate', width: 120 },
    {
      title: '模型',
      dataIndex: 'model',
      key: 'model',
      render: (value: string | null) =>
        value ? (
          <Tag color={MODEL_TAG_COLOR[value] ?? 'blue'}>{value}</Tag>
        ) : (
          '-'
        ),
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
      dataIndex: 'generatedAt',
      key: 'generatedAt',
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
      title: '用户副本',
      dataIndex: 'userCopyCount',
      key: 'userCopyCount',
      width: 90,
      render: (value: number) => (value > 0 ? `${value}` : '-'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 280,
      render: (_: unknown, record: AdminMarketReviewItem) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>
            编辑
          </Button>
          <Button
            size="small"
            icon={<RobotOutlined />}
            loading={generatingDate === record.tradeDate}
            disabled={generatingDate !== null && generatingDate !== record.tradeDate}
            onClick={() => handleRegenerate(record)}
          >
            AI 重新生成
          </Button>
          <Popconfirm
            title={`删除 ${record.tradeDate} 全部 ${record.historyCount} 条生成记录？`}
            description="删除后可重新生成；用户编辑副本将保留"
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

  return (
    <Card
      title="复盘管理"
      variant="borderless"
      extra={
        <Space>
          <DatePicker.RangePicker
            value={
              dateRange[0] && dateRange[1]
                ? ([dayjs(dateRange[0]), dayjs(dateRange[1])] as [Dayjs, Dayjs])
                : null
            }
            onChange={handleRangeChange}
            allowEmpty={[true, true]}
          />
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            新增复盘
          </Button>
        </Space>
      }
    >
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
        每个交易日显示最新一条生成记录；删除会清空该日全部生成记录（共享 base），用户编辑副本保留。
      </Typography.Paragraph>
      <Table
        dataSource={listQuery.data?.items ?? []}
        columns={columns}
        rowKey="tradeDate"
        loading={listQuery.isLoading}
        scroll={{ x: 'max-content' }}
        pagination={{
          current: page,
          pageSize,
          total: listQuery.data?.total ?? 0,
          showSizeChanger: true,
          showTotal: (total) => `共 ${total} 个交易日`,
          onChange: (p, ps) => {
            setPage(p)
            setPageSize(ps)
          },
        }}
      />
      <MarketReviewAdminModal
        open={modalOpen}
        tradeDate={editingDate}
        onCancel={() => setModalOpen(false)}
        onAIAsk={(d) => startGenerate(d, false)}
      />
    </Card>
  )
}
