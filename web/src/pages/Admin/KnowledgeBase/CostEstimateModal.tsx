import { Alert, Button, Modal, Table, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import type { ApiKbCostEstimateItem, ApiKbCostEstimateResponse } from '@ai-invest/shared'

const KIND_LABEL: Record<string, string> = {
  video: '视频',
  audio: '音频',
  book: '电子书',
}

const columns: ColumnsType<ApiKbCostEstimateItem> = [
  { title: '素材', dataIndex: 'title', ellipsis: true },
  {
    title: '类型',
    dataIndex: 'mediaKind',
    width: 80,
    render: (kind: string) => KIND_LABEL[kind] ?? kind,
  },
  {
    title: '时长',
    dataIndex: 'durationSeconds',
    width: 100,
    render: (s: number | null) =>
      s == null ? '-' : `${Math.floor(s / 60)} 分 ${s % 60} 秒`,
  },
  {
    title: 'ASR 费用（元）',
    dataIndex: 'asrCost',
    width: 130,
    align: 'right',
    render: (v: number) => v.toFixed(2),
  },
  {
    title: '清洗 tokens（估）',
    dataIndex: 'cleanTokens',
    width: 140,
    align: 'right',
    render: (v: number) => v.toLocaleString('zh-CN'),
  },
  {
    title: '预估合计（元）',
    dataIndex: 'estimatedCost',
    width: 130,
    align: 'right',
    render: (v: number) => v.toFixed(2),
  },
]

export function CostEstimateModal({
  open,
  loading,
  estimate,
  confirming,
  onCancel,
  onConfirm,
}: {
  open: boolean
  loading: boolean
  estimate: ApiKbCostEstimateResponse | null
  confirming: boolean
  onCancel: () => void
  onConfirm: () => void
}) {
  return (
    <Modal
      title="费用预估"
      open={open}
      onCancel={onCancel}
      width={720}
      footer={[
        <Typography.Text key="total" className="mr-4">
          合计：
          <Typography.Text strong>￥{(estimate?.total ?? 0).toFixed(2)}</Typography.Text>
        </Typography.Text>,
        <Button key="cancel" onClick={onCancel}>
          取消
        </Button>,
        <Button
          key="confirm"
          type="primary"
          loading={confirming}
          disabled={!estimate || estimate.items.length === 0}
          onClick={onConfirm}
        >
          确认费用并入队
        </Button>,
      ]}
    >
      <Alert
        type="info"
        showIcon
        className="mb-3"
        message="预估即接受以下计费口径：ASR 按音频时长、清洗按字数折算 tokens；确认后素材进入转写队列。"
      />
      <Table
        size="small"
        rowKey="mediaId"
        columns={columns}
        dataSource={estimate?.items ?? []}
        loading={loading}
        pagination={false}
        scroll={{ y: 360 }}
      />
    </Modal>
  )
}
