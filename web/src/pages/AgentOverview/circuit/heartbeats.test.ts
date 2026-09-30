import { describe, expect, it } from 'vitest'

import type { CeleryTaskSquare } from '@ai-invest/shared'

import { counterHeartbeat, domainHeartbeat } from './heartbeats'

const FINISHED = '2026-09-30T05:40:00+00:00' // 13:40 北京

function task(overrides: Partial<CeleryTaskSquare>): CeleryTaskSquare {
  return {
    key: 'k',
    taskType: 'kb_extract',
    label: '知识库抽取',
    state: 'success',
    source: null,
    startedAt: null,
    finishedAt: FINISHED,
    durationMs: null,
    detail: null,
    ...overrides,
  }
}

describe('domainHeartbeat', () => {
  it('命中关键词 + 今日成功 → 最近成功 HH:mm', () => {
    const beat = domainHeartbeat([task({})], ['kb', 'extract'], '2026-09-30')
    expect(beat).toBe('最近成功 13:40')
  })

  it('执行中优先于历史成功', () => {
    const beat = domainHeartbeat(
      [task({}), task({ state: 'running', label: '资讯采集', finishedAt: null })],
      ['资讯'],
      '2026-09-30',
    )
    expect(beat).toBe('执行中 · 资讯采集')
  })

  it('无命中任务 → 今日静默（不虚报在线）', () => {
    expect(domainHeartbeat([task({})], ['sentiment', '抖音'], '2026-09-30')).toBe('今日静默')
  })

  it('成功但非今日 → 今日静默', () => {
    expect(domainHeartbeat([task({})], ['kb'], '2026-10-08')).toBe('今日静默')
  })
})

describe('counterHeartbeat', () => {
  it('up + 延迟 → HB 毫秒', () => {
    expect(
      counterHeartbeat({ key: 'counter', name: '柜台', category: 'external', status: 'up', latencyMs: 320, detail: null, error: null }),
    ).toEqual({ up: true, text: 'HB 320ms' })
  })

  it('down → 离线（附错误）', () => {
    const beat = counterHeartbeat({ key: 'counter', name: '柜台', category: 'external', status: 'down', latencyMs: null, detail: null, error: '超时' })
    expect(beat.up).toBe(false)
    expect(beat.text).toContain('离线')
  })

  it('无数据 → 状态未知', () => {
    expect(counterHeartbeat(undefined)).toEqual({ up: null, text: '状态未知' })
  })
})
