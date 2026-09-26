import { CalendarOutlined, ReloadOutlined } from '@ant-design/icons'
import {
  Alert,
  Button,
  Calendar,
  Card,
  Flex,
  Input,
  Modal,
  Popconfirm,
  Space,
  Spin,
  Switch,
  Tag,
  Typography,
  message,
} from 'antd'
import type { Dayjs } from 'dayjs'
import { useMemo, useState } from 'react'

import type { ApiTradeCalendarDay } from '@ai-invest/shared'

import {
  useSeedTradeCalendar,
  useToggleTradeCalendarDay,
  useTradeCalendarYear,
} from '@/hooks/useTradeCalendar'
import { bjNow } from '@/utils/beijing'

const DATE_FORMAT = 'YYYY-MM-DD'
const WEEKDAY_LABELS = '日一二三四五六'

export function TradeCalendar() {
  const [year, setYear] = useState(() => bjNow().year())
  const [modalDay, setModalDay] = useState<Dayjs | null>(null)
  const [modalIsTrading, setModalIsTrading] = useState(true)
  const [modalRemark, setModalRemark] = useState('')

  const { data, isLoading } = useTradeCalendarYear(year)
  const toggleMutation = useToggleTradeCalendarDay(year)
  const seedMutation = useSeedTradeCalendar()

  const dayMap = useMemo(() => {
    const map = new Map<string, ApiTradeCalendarDay>()
    for (const day of data?.days ?? []) map.set(day.calendarDate, day)
    return map
  }, [data])

  const notCovered = !isLoading && !data?.coverage.minDate

  const openEdit = (value: Dayjs) => {
    if (value.isBefore(bjNow().startOf('day'))) {
      message.warning('不可修改历史日期的日历口径')
      return
    }
    const existing = dayMap.get(value.format(DATE_FORMAT))
    setModalIsTrading(existing?.isTrading ?? value.day() < 5)
    setModalRemark(existing?.remark ?? '')
    setModalDay(value)
  }

  const handleSave = async () => {
    if (!modalDay) return
    try {
      await toggleMutation.mutateAsync({
        day: modalDay.format(DATE_FORMAT),
        isTrading: modalIsTrading,
        remark: modalRemark || null,
      })
      message.success(`${modalDay.format(DATE_FORMAT)} 已标记为${modalIsTrading ? '交易日' : '非交易日'}`)
      setModalDay(null)
    } catch {
      message.error('保存失败')
    }
  }

  const handleSeed = async () => {
    try {
      const result = await seedMutation.mutateAsync(undefined)
      message.success(`日历已刷新，写入 ${result.written} 行（${result.years.join('、')} 年）`)
    } catch {
      message.error('日历刷新失败（新浪数据源异常？）')
    }
  }

  const cellRender = (value: Dayjs) => {
    if (value.year() !== year) return null
    const day = dayMap.get(value.format(DATE_FORMAT))
    if (!day) {
      return (
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          无数据
        </Typography.Text>
      )
    }
    if (day.source === 'manual') {
      return (
        <Space size={4}>
          <Tag color={day.isTrading ? 'green' : 'red'} style={{ marginInlineEnd: 0 }}>
            {day.isTrading ? '交易' : '休市'}
          </Tag>
          <Tag color="gold" style={{ marginInlineEnd: 0 }}>手动</Tag>
        </Space>
      )
    }
    return (
      <Tag color={day.isTrading ? 'green' : 'red'} style={{ marginInlineEnd: 0 }}>
        {day.isTrading ? '交易' : '休市'}
      </Tag>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {notCovered && (
        <Alert
          type="warning"
          showIcon
          message={`${year} 年无交易日历覆盖`}
          description="trade_day_only 采集任务在无覆盖期间将被拒绝调度。请点击「重新生成日历」初始化（缺省覆盖当年 + 下一年）。"
        />
      )}

      <Card
        title={
          <Space>
            <CalendarOutlined />
            <span>交易日历</span>
          </Space>
        }
        extra={
          <Popconfirm
            title="重新生成日历？"
            description="按新浪交易日历重建当年与下一年种子行，人工覆盖行不受影响"
            onConfirm={handleSeed}
          >
            <Button icon={<ReloadOutlined />} loading={seedMutation.isPending}>
              重新生成日历
            </Button>
          </Popconfirm>
        }
      >
        <Flex vertical gap={8}>
          {data?.coverage.minDate && (
            <Typography.Text type="secondary">
              {year} 年覆盖 {data.coverage.minDate} ~ {data.coverage.maxDate}：
              交易日 {data.coverage.tradingDays} 天，非交易日 {data.coverage.nonTradingDays} 天
            </Typography.Text>
          )}
          <Typography.Text type="secondary">
            点击当天及以后的日期可人工调整口径（调休上班 / 临时休市）；种子刷新不回改人工覆盖行。
          </Typography.Text>
        </Flex>
      </Card>

      <Card>
        {isLoading ? (
          <div style={{ textAlign: 'center', padding: 48 }}>
            <Spin />
          </div>
        ) : (
          <Calendar
            fullscreen
            cellRender={(current, info) => {
              if (info.type !== 'date') return info.originNode
              return cellRender(current)
            }}
            onSelect={openEdit}
            onPanelChange={(value) => {
              if (value.year() !== year) setYear(value.year())
            }}
          />
        )}
      </Card>

      <Modal
        title={
          modalDay
            ? `${modalDay.format(DATE_FORMAT)}（周${WEEKDAY_LABELS[modalDay.day()]}）`
            : ''
        }
        open={modalDay !== null}
        onOk={handleSave}
        onCancel={() => setModalDay(null)}
        okText="保存"
        cancelText="取消"
        confirmLoading={toggleMutation.isPending}
      >
        <Flex vertical gap={12}>
          <Space>
            <Switch
              checked={modalIsTrading}
              checkedChildren="交易日"
              unCheckedChildren="非交易日"
              onChange={setModalIsTrading}
            />
            <Typography.Text>{modalIsTrading ? '视为交易日（如调休上班）' : '视为非交易日（如临时休市）'}</Typography.Text>
          </Space>
          <Input
            placeholder="备注（如：中秋调休、临时休市）"
            value={modalRemark}
            maxLength={200}
            onChange={(e) => setModalRemark(e.target.value)}
          />
        </Flex>
      </Modal>
    </div>
  )
}
