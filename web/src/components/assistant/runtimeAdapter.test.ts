/**
 * 助手运行时防腐层契约测试：钉死 SDK 回调签名与事件分派行为。
 *
 * 背景（两类历史事故，本测试防复发）：
 * - onCustomEvent 回调实际签名 (eventType, data)，接成单参曾致 custom 通路
 *   长期静默失效（问题卡不渲染）；
 * - custom 与 updates 双通道会送达同一标记，分派必须幂等。
 */
import { describe, expect, it } from 'vitest'

import { useAssistantStore } from '@/stores/assistant'

import { createAssistantRuntimeAdapter } from './runtimeAdapter'

const question = (text: string) => ({
  type: 'question',
  question: text,
  options: [
    { value: 'append', label: '保留并新增' },
    { value: 'replace', label: '覆盖 AI 画线' },
  ],
  default: 'append',
})

const questionUpdates = (payload: ReturnType<typeof question>) => ({
  tools: {
    messages: [
      {
        type: 'tool',
        content: JSON.stringify({ __question__: payload, note: '问题卡已发送。' }),
      },
    ],
  },
})

describe('runtimeAdapter 事件契约', () => {
  it('onCustomEvent 签名为 (eventType, data)：question 载荷渲染问题卡', () => {
    useAssistantStore.setState({ questionCard: null })
    const { eventHandlers } = createAssistantRuntimeAdapter()
    eventHandlers.onCustomEvent('custom', question('检测到已有画线，如何处理？'))
    const card = useAssistantStore.getState().questionCard
    expect(card?.question).toBe('检测到已有画线，如何处理？')
    expect(card?.options).toHaveLength(2)
    expect(card?.default).toBe('append')
  })

  it('custom 通道的已注册页面事件写入 pageResult', () => {
    useAssistantStore.setState({ pageResult: null })
    const { eventHandlers } = createAssistantRuntimeAdapter()
    eventHandlers.onCustomEvent('custom', {
      type: 'kline_drawing.complete',
      target_type: 'stock',
      target_code: '600519',
      period: 'daily',
      count: 3,
    })
    expect(useAssistantStore.getState().pageResult?.type).toBe('kline_drawing.complete')
  })

  it('updates 通道的问题标记同样渲染问题卡', () => {
    useAssistantStore.setState({ questionCard: null })
    const { eventHandlers } = createAssistantRuntimeAdapter()
    eventHandlers.onUpdates(questionUpdates(question('updates 通道的问题？')))
    expect(useAssistantStore.getState().questionCard?.question).toBe('updates 通道的问题？')
  })

  it('双通道送达同一问题标记只生效一次（幂等）', () => {
    useAssistantStore.setState({ questionCard: null })
    let notifications = 0
    const unsub = useAssistantStore.subscribe(() => {
      notifications += 1
    })
    try {
      const { eventHandlers } = createAssistantRuntimeAdapter()
      const payload = question('双通道幂等验证问题？')
      eventHandlers.onCustomEvent('custom', payload)
      eventHandlers.onUpdates(questionUpdates(payload))
      eventHandlers.onCustomEvent('custom', payload)
      expect(notifications).toBe(1)
      expect(useAssistantStore.getState().questionCard?.question).toBe('双通道幂等验证问题？')
    } finally {
      unsub()
    }
  })

  it('畸形载荷与未注册类型安全忽略', () => {
    useAssistantStore.setState({ questionCard: null, pageResult: null })
    const { eventHandlers } = createAssistantRuntimeAdapter()
    expect(() => eventHandlers.onCustomEvent('custom', { type: 'question', options: [] })).not.toThrow()
    expect(() => eventHandlers.onCustomEvent('custom', 'not-an-object')).not.toThrow()
    expect(() => eventHandlers.onCustomEvent('custom', { type: 'unknown.event' })).not.toThrow()
    expect(() => eventHandlers.onUpdates({ node: { messages: [{ type: 'tool', content: 'ok' }] } })).not.toThrow()
    expect(useAssistantStore.getState().questionCard).toBeNull()
    expect(useAssistantStore.getState().pageResult).toBeNull()
  })

  it('adapter 引用契约：threadListAdapter/eventHandlers/load/stream 齐备', () => {
    const adapter = createAssistantRuntimeAdapter()
    expect(typeof adapter.load).toBe('function')
    expect(typeof adapter.stream).toBe('function')
    expect(typeof adapter.threadListAdapter.initialize).toBe('function')
    expect(typeof adapter.eventHandlers.onUpdates).toBe('function')
    expect(typeof adapter.eventHandlers.onCustomEvent).toBe('function')
  })
})
