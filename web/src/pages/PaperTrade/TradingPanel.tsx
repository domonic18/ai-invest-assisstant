import { Alert, AutoComplete, Button, Card, Form, Input, InputNumber, Modal, Select, Tag, Tooltip } from 'antd'
import { useEffect, useMemo, useState } from 'react'

import type {
  ApiPaperTradeAccount,
  ApiPaperTradePosition,
} from '@ai-invest/shared'

import {
  useDelayedPaperTradeSync,
  usePlacePaperTradeOrder,
} from '@/hooks/usePaperTrade'
import { useStockQuote, useStockSearch } from '@/hooks/useStocks'
import { bjNow } from '@/utils/beijing'
import {
  changeColor,
  fallColor,
  formatPercent,
  riseColor,
} from '@/utils/formatters'

import {
  limitPrices,
  maxBuyVolume,
  maxSellVolume,
  marketSession,
  priceLimitPct,
  SESSION_LABEL,
} from './tradingRules'

interface OrderFormValues {
  symbol: string
  side: 'buy' | 'sell'
  orderType: 'limit' | 'market'
  price?: number
  volume: number
}

/** 持仓行/外部入口回填下单卡的载荷（symbol 用 6 位代码）。 */
export interface OrderPrefill {
  symbol: string
  side: 'buy' | 'sell'
  price?: number
  volume?: number
}

interface TradingPanelProps {
  account: ApiPaperTradeAccount
  cashAvailable?: number | null
  positions?: ApiPaperTradePosition[]
  prefill?: OrderPrefill | null
  onPrefillConsumed?: () => void
}

/** 提取平台规范的 6 位股票代码（行情查询与下单提交共用）；
 * 接受裸代码或粘贴的带前缀代码（SZSE.000037）。柜台前缀由后端按主数据解析。 */
function stockCode(raw: string | undefined): string {
  const match = raw?.trim().toUpperCase().match(/(\d{6})/)
  return match ? match[1] : ''
}

function findPosition(
  positions: ApiPaperTradePosition[] | undefined,
  code: string,
): ApiPaperTradePosition | undefined {
  if (!code) return undefined
  return positions?.find(
    (p) => p.stockCode === code || p.symbol.endsWith(code),
  )
}

const SESSION_TAG_COLOR: Record<string, string> = {
  success: 'green',
  warning: 'orange',
  default: 'default',
}

/** 快捷仓位档位：按最大可买/可卖取比例，再整手取整。 */
const QUICK_RATIOS: { label: string; ratio: number }[] = [
  { label: '1/4仓', ratio: 0.25 },
  { label: '半仓', ratio: 0.5 },
  { label: '3/4仓', ratio: 0.75 },
  { label: '全仓', ratio: 1 },
]

/** 下单面板（同花顺式竖排）：买卖双 tab + 代码联想 + 快捷仓位 + 涨跌停/资金校验 + 确认弹窗。 */
export function TradingPanel({
  account,
  cashAvailable,
  positions,
  prefill,
  onPrefillConsumed,
}: TradingPanelProps) {
  const [form] = Form.useForm<OrderFormValues>()
  const placeMutation = usePlacePaperTradeOrder()
  const scheduleSync = useDelayedPaperTradeSync()
  const [now, setNow] = useState(() => bjNow())
  const [searchQ, setSearchQ] = useState('')

  // 30s 心跳刷新交易时段徽标（行情轮询本身也会带来重渲染）
  useEffect(() => {
    const timer = setInterval(() => setNow(bjNow()), 30_000)
    return () => clearInterval(timer)
  }, [])

  // 持仓行「买入/卖出」联动：回填后立即消费，避免重复触发
  useEffect(() => {
    if (!prefill) return
    form.setFieldsValue({
      symbol: prefill.symbol,
      side: prefill.side,
      ...(prefill.price != null ? { price: prefill.price } : {}),
      ...(prefill.volume != null ? { volume: prefill.volume } : {}),
    })
    onPrefillConsumed?.()
  }, [prefill, form, onPrefillConsumed])

  const [orderType, setOrderType] = useState<'limit' | 'market'>('limit')
  const symbol = Form.useWatch('symbol', form)
  const side = (Form.useWatch('side', form) ?? 'buy') as 'buy' | 'sell'
  const price = Form.useWatch('price', form)

  const code = stockCode(symbol)
  const quoteQuery = useStockQuote(/^\d{6}$/.test(code) ? code : '')
  const quote = quoteQuery.data
  const searchQuery = useStockSearch(searchQ)
  const symbolOptions = useMemo(
    () =>
      (searchQuery.data ?? []).map((s) => ({
        value: s.code,
        label: (
          <div className="flex items-center justify-between gap-3">
            <span>
              {s.code} <span className="ml-1">{s.name}</span>
            </span>
            <span className="text-xs text-white/40">{s.market}</span>
          </div>
        ),
      })),
    [searchQuery.data],
  )

  const session = marketSession(now)
  const sessionInfo = SESSION_LABEL[session]

  const position = findPosition(positions, code)
  const limitPct = quote?.prevClose
    ? priceLimitPct(quote.name, code)
    : null
  const limits =
    quote?.prevClose != null && limitPct != null
      ? limitPrices(Number(quote.prevClose), limitPct)
      : null

  const effectivePrice =
    orderType === 'limit' && price ? Number(price) : quote?.price ?? null
  const maxBuy =
    side === 'buy' && cashAvailable != null && effectivePrice
      ? maxBuyVolume(Number(cashAvailable), effectivePrice)
      : null
  const maxSell =
    side === 'sell' ? maxSellVolume(position?.availableVolume ?? 0) : null

  const tradable = !account.agentKey && account.isEnabled

  const validatePrice = (_rule: unknown, value: number | undefined) => {
    if (orderType !== 'limit') return Promise.resolve()
    if (value == null) return Promise.reject(new Error('限价单必须带价格'))
    if (limits) {
      if (value > limits.limitUp)
        return Promise.reject(
          new Error(`超过涨停价 ${limits.limitUp.toFixed(2)}，将被柜台拒单`),
        )
      if (value < limits.limitDown)
        return Promise.reject(
          new Error(`低于跌停价 ${limits.limitDown.toFixed(2)}，将被柜台拒单`),
        )
    }
    return Promise.resolve()
  }

  const validateVolume = (_rule: unknown, value: number | undefined) => {
    if (value == null) return Promise.reject(new Error('输入数量'))
    if (value % 100 !== 0)
      return Promise.reject(new Error('数量须为 100 股整数倍'))
    if (side === 'sell') {
      if (!position || (position.availableVolume ?? 0) <= 0)
        return Promise.reject(new Error('该标的无可卖持仓（T+1 未可用亦不可卖）'))
      if (maxSell != null && value > maxSell)
        return Promise.reject(new Error(`超过最大可卖 ${maxSell} 股`))
    } else if (maxBuy != null && value > maxBuy) {
      return Promise.reject(
        new Error(`资金不足，最大可买 ${maxBuy} 股`),
      )
    }
    return Promise.resolve()
  }

  const doPlace = async (values: OrderFormValues) => {
    try {
      await placeMutation.mutateAsync({
        accountId: account.id,
        symbol: stockCode(values.symbol),
        side: values.side,
        volume: values.volume,
        orderType: values.orderType,
        price: values.orderType === 'limit' ? (values.price ?? 0) : 0,
      })
      form.resetFields(['symbol', 'price', 'volume'])
      setSearchQ('')
      scheduleSync(account.id)
    } catch {
      // 柜台拒单/403 已由 mutation onError 弹窗
    }
  }

  const handleFinish = (values: OrderFormValues) => {
    const sideLabel = values.side === 'buy' ? '买入' : '卖出'
    const amount =
      values.orderType === 'limit' && values.price
        ? `（金额 ${(values.price * values.volume).toFixed(2)}）`
        : ''
    Modal.confirm({
      title: '确认下单',
      okText: '确认下单',
      cancelText: '再想想',
      content: (
        <div className="space-y-1 pt-2 text-sm">
          <div>
            标的：{stockCode(values.symbol)}
            {quote?.name ? `（${quote.name}）` : ''}
          </div>
          <div>
            方向：
            <span
              style={{
                color: values.side === 'buy' ? riseColor() : fallColor(),
              }}
            >
              {sideLabel}
            </span>
            ；{values.orderType === 'limit' ? `限价 ${values.price}` : '市价'}
            ；{values.volume} 股{amount}
          </div>
          {session !== 'open' && (
            <Alert type="warning" showIcon message={`${sessionInfo.label}：${sessionInfo.hint}`} />
          )}
        </div>
      ),
      onOk: () => doPlace(values),
    })
  }

  const sideColor = side === 'buy' ? riseColor() : fallColor()
  const quickBase = side === 'buy' ? maxBuy : maxSell
  const applyRatio = (ratio: number) => {
    if (quickBase == null) return
    form.setFieldsValue({ volume: Math.floor((quickBase * ratio) / 100) * 100 })
  }

  const quoteRow = (label: string, value: string, color?: string) => (
    <span className="text-xs">
      <span className="text-white/50">{label} </span>
      <span style={color ? { color } : undefined}>{value}</span>
    </span>
  )

  return (
    <Card
      size="small"
      title="下单"
      extra={
        <Tooltip title={sessionInfo.hint}>
          <Tag color={SESSION_TAG_COLOR[sessionInfo.tone]}>{sessionInfo.label}</Tag>
        </Tooltip>
      }
    >
      {!tradable ? (
        <Alert
          type={account.agentKey ? 'info' : 'warning'}
          showIcon
          message={account.agentKey ? 'Agent 专属账户' : '账户已停用'}
          description={
            account.agentKey
              ? '该账户由交易 agent 自动交易，不支持人工下单。'
              : '启用该账户后即可在此下单。'
          }
        />
      ) : (
        <div className="space-y-2">
          <div className="grid grid-cols-2 gap-2">
            {(['buy', 'sell'] as const).map((s) => {
              const active = side === s
              const color = s === 'buy' ? riseColor() : fallColor()
              return (
                <Button
                  key={s}
                  block
                  onClick={() => form.setFieldsValue({ side: s })}
                  style={
                    active
                      ? { background: color, borderColor: color, color: '#fff' }
                      : { borderColor: color, color }
                  }
                >
                  {s === 'buy' ? '买入' : '卖出'}
                </Button>
              )
            })}
          </div>
          <Form<OrderFormValues>
            form={form}
            layout="vertical"
            onFinish={(values) => void handleFinish(values)}
            initialValues={{ side: 'buy', orderType: 'limit' }}
            className="[&_.ant-form-item]:mb-2"
          >
            <Form.Item name="side" hidden>
              <Input />
            </Form.Item>
            <Form.Item name="symbol" label="代码" className="mb-2!">
              <AutoComplete
                options={symbolOptions}
                allowClear
                onSearch={(v) => setSearchQ(v.trim())}
                onSelect={() => setSearchQ('')}
                onClear={() => setSearchQ('')}
                placeholder="代码/名称，如 000037"
              />
            </Form.Item>
            {quote && (
              <div className="-mt-1 mb-2 flex flex-wrap items-center gap-x-3 gap-y-0.5">
                <span className="text-sm font-medium" style={{ color: changeColor(quote.changePct) }}>
                  {quote.price != null ? Number(quote.price).toFixed(2) : '-'}
                </span>
                {quote.changePct != null && (
                  <span className="text-xs" style={{ color: changeColor(quote.changePct) }}>
                    {formatPercent(quote.changePct)}
                  </span>
                )}
                {quoteRow('昨收', quote.prevClose != null ? Number(quote.prevClose).toFixed(2) : '-')}
                {limits && quoteRow('涨停', limits.limitUp.toFixed(2), riseColor())}
                {limits && quoteRow('跌停', limits.limitDown.toFixed(2), fallColor())}
              </div>
            )}
            <div className="flex items-start gap-2">
              <Form.Item name="orderType" label="类型" className="w-[88px] shrink-0">
                <Select
                  onChange={(v: 'limit' | 'market') => setOrderType(v)}
                  options={[
                    { value: 'limit', label: '限价' },
                    { value: 'market', label: '市价' },
                  ]}
                />
              </Form.Item>
              <Form.Item
                name="price"
                label="价格"
                className="min-w-0 flex-1"
                rules={
                  orderType === 'limit'
                    ? [{ required: true, message: '限价单必须带价格' }, { validator: validatePrice }]
                    : []
                }
              >
                <InputNumber
                  placeholder="价格"
                  min={0}
                  step={0.01}
                  style={{ width: '100%' }}
                  disabled={orderType === 'market'}
                />
              </Form.Item>
            </div>
            <Form.Item
              name="volume"
              label="数量（股）"
              className="mb-2!"
              rules={[{ required: true, message: '输入数量' }, { validator: validateVolume }]}
            >
              <InputNumber placeholder="数量" min={0} step={100} style={{ width: '100%' }} />
            </Form.Item>
            <div className="mb-2 grid grid-cols-4 gap-2">
              {QUICK_RATIOS.map(({ label, ratio }) => (
                <Button
                  key={label}
                  size="small"
                  disabled={quickBase == null || quickBase <= 0}
                  onClick={() => applyRatio(ratio)}
                >
                  {label}
                </Button>
              ))}
            </div>
            <div className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs">
              {orderType === 'limit' && quote?.price != null && (
                <Button
                  type="link"
                  size="small"
                  className="px-0"
                  onClick={() => form.setFieldValue('price', quote?.price)}
                >
                  现价代入
                </Button>
              )}
              {side === 'buy'
                ? maxBuy != null && quoteRow('最大可买', `${maxBuy} 股`)
                : maxSell != null && (
                    <Button
                      type="link"
                      size="small"
                      className="px-0"
                      disabled={maxSell <= 0}
                      onClick={() => form.setFieldValue('volume', maxSell)}
                    >
                      最大可卖 {maxSell} 股{maxSell <= 0 ? '（无可用持仓）' : ''}
                    </Button>
                  )}
              {side === 'sell' && code && !position && (
                <span className="text-white/50">该标的无持仓，请切换为买入</span>
              )}
            </div>
            <Button
              block
              type="primary"
              htmlType="submit"
              loading={placeMutation.isPending}
              style={{ background: sideColor, borderColor: sideColor }}
            >
              下 单
            </Button>
          </Form>
        </div>
      )}
    </Card>
  )
}
