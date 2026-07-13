import {
  CaretRightOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons'
import {
  Alert,
  Button,
  Checkbox,
  Collapse,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Spin,
  Tag,
  Typography,
} from 'antd'
import { useEffect, useMemo } from 'react'

import { useCollectorTaskChannels } from '@/hooks/useCollectorAdmin'
import type {
  CollectorTaskName,
  CollectorTaskOption,
  CollectorTaskRunOptions,
} from '@ai-invest/shared'

interface CollectorTaskModalProps {
  open: boolean
  task: CollectorTaskOption | null
  onCancel: () => void
  onSubmit: (taskName: CollectorTaskName, options: CollectorTaskRunOptions) => void
  loading: boolean
}

interface TaskFormValues {
  preferredSource?: string
  symbols?: string
  period?: string
  startDate?: string
  endDate?: string
  sectorType?: string
  indicators?: string[]
}

const PERIOD_OPTIONS = [
  { value: 'daily', label: '日线' },
  { value: 'minute', label: '分钟线' },
]

const SECTOR_TYPE_OPTIONS = [
  { value: 'industry', label: '行业' },
  { value: 'concept', label: '概念' },
  { value: 'region', label: '地域' },
]

const MACRO_INDICATOR_OPTIONS = [
  { value: 'cpi', label: 'CPI' },
  { value: 'pmi', label: 'PMI' },
  { value: 'gdp', label: 'GDP' },
]

function parseSymbols(input: string | undefined): string[] | undefined {
  if (!input) return undefined
  const symbols = input
    .split(/[,，\s]+/)
    .map((s) => s.trim())
    .filter(Boolean)
  return symbols.length > 0 ? symbols : undefined
}

export function CollectorTaskModal({
  open,
  task,
  onCancel,
  onSubmit,
  loading,
}: CollectorTaskModalProps) {
  const [form] = Form.useForm<TaskFormValues>()
  const { data, isLoading, error } = useCollectorTaskChannels(task?.key ?? null)

  const channelOptions = useMemo(
    () =>
      data?.channels.map((channel) => ({
        value: channel.source,
        label: `${channel.name} (${channel.source})`,
      })) ?? [],
    [data],
  )

  useEffect(() => {
    if (open && data) {
      form.setFieldsValue({
        preferredSource: data.resolved_source ?? undefined,
        symbols: undefined,
        period: 'daily',
        startDate: undefined,
        endDate: undefined,
        sectorType: 'industry',
        indicators: ['cpi', 'pmi', 'gdp'],
      })
    }
  }, [open, data, form])

  const handleOk = async () => {
    const values = await form.validateFields()
    if (task) {
      onSubmit(task.key, {
        preferredSource: values.preferredSource,
        symbols: parseSymbols(values.symbols),
        period: values.period,
        startDate: values.startDate,
        endDate: values.endDate,
        sectorType: values.sectorType,
        indicators: values.indicators,
      })
    }
  }

  return (
    <Modal
      title={task ? `触发：${task.label}` : '触发采集任务'}
      open={open}
      onOk={handleOk}
      onCancel={onCancel}
      confirmLoading={loading}
      destroyOnClose
      footer={[
        <Button key="cancel" onClick={onCancel}>
          取消
        </Button>,
        <Button
          key="run"
          type="primary"
          icon={<CaretRightOutlined />}
          loading={loading}
          onClick={handleOk}
        >
          开始采集
        </Button>,
      ]}
    >
      {error ? (
        <Alert
          message="加载可用渠道失败"
          description={error instanceof Error ? error.message : '未知错误'}
          type="error"
          showIcon
        />
      ) : isLoading || !data ? (
        <Space className="py-8" size="middle">
          <Spin />
          <Typography.Text type="secondary">正在解析可用渠道...</Typography.Text>
        </Space>
      ) : (
        <Form form={form} layout="vertical" autoComplete="off">
          <Alert
            message={
              <Space>
                <ExclamationCircleOutlined />
                <span>
                  将使用渠道：
                  <Tag color="blue">
                    {data.resolved_source
                      ? data.channels.find((c) => c.source === data.resolved_source)?.name ??
                        data.resolved_source
                      : '无可用渠道'}
                  </Tag>
                </span>
              </Space>
            }
            type="info"
            showIcon={false}
            className="mb-4"
          />

          <Form.Item label="指定渠道（可选）" name="preferredSource">
            <Select
              allowClear
              placeholder="留空则系统自动选择"
              options={channelOptions}
              disabled={channelOptions.length === 0}
            />
          </Form.Item>

          <Collapse
            ghost
            items={[
              {
                key: 'advanced',
                label: '高级选项',
                children: (
                  <>
                    {task?.key === 'kline' && (
                      <Form.Item label="周期" name="period">
                        <Select options={PERIOD_OPTIONS} />
                      </Form.Item>
                    )}
                    {(task?.key === 'disclosure' || task?.key === 'dragon-list') && (
                      <>
                        <Form.Item label="开始日期" name="startDate">
                          <Input placeholder="YYYY-MM-DD" />
                        </Form.Item>
                        <Form.Item label="结束日期" name="endDate">
                          <Input placeholder="YYYY-MM-DD" />
                        </Form.Item>
                      </>
                    )}
                    {task?.key === 'sector-fund-flow' && (
                      <Form.Item label="板块类型" name="sectorType">
                        <Select options={SECTOR_TYPE_OPTIONS} />
                      </Form.Item>
                    )}
                    {task?.key === 'macro' && (
                      <Form.Item label="指标" name="indicators">
                        <Checkbox.Group options={MACRO_INDICATOR_OPTIONS} />
                      </Form.Item>
                    )}
                    <Form.Item
                      label="股票代码"
                      name="symbols"
                      help="逗号分隔，留空则使用默认股票列表"
                    >
                      <Input.TextArea
                        rows={2}
                        placeholder="000001,000002,600000"
                      />
                    </Form.Item>
                  </>
                ),
              },
            ]}
          />
        </Form>
      )}
    </Modal>
  )
}
