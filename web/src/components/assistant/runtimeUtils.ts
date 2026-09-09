import type { PageAssistantResult, TodoStep } from '@/stores/assistant'

import { parsePageEvent } from './pageEvents'

type StateWithTasks = {
  tasks?: Array<{ interrupts?: Array<Record<string, unknown>> }>
}

/** 从根图 updates 载荷（{node: state_update}）中提取 deepagents todos */
export function extractTodos(updates: unknown): TodoStep[] | undefined {
  if (typeof updates !== 'object' || updates === null) return undefined
  for (const node of Object.values(updates as Record<string, unknown>)) {
    if (typeof node !== 'object' || node === null) continue
    const todos = (node as Record<string, unknown>).todos
    if (Array.isArray(todos)) return todos as TodoStep[]
  }
  return undefined
}

/** 从工具结果/ToolMessage content（对象或 JSON 字符串）中提取 __event__ 标记。 */
export function extractEventMarker(content: unknown): Record<string, unknown> | null {
  let raw = content
  if (typeof raw === 'string') {
    try {
      raw = JSON.parse(raw)
    } catch {
      return null
    }
  }
  if (typeof raw !== 'object' || raw === null) return null
  const event = (raw as Record<string, unknown>).__event__
  if (typeof event !== 'object' || event === null) return null
  return event as Record<string, unknown>
}

/** 从 messages 列表或 updates 中提取已注册的页面回写事件。 */
export function extractPageResultFromMessages(
  messages: unknown[],
): PageAssistantResult | null {
  for (const msg of messages) {
    if (typeof msg !== 'object' || msg === null) continue
    const typed = msg as Record<string, unknown>
    if (typed.type !== 'tool') continue
    const event = extractEventMarker(typed.content)
    if (!event) continue
    const parsed = parsePageEvent(event)
    if (parsed) return parsed.result
  }
  return null
}

export function extractPageResult(updates: unknown): PageAssistantResult | null {
  if (typeof updates !== 'object' || updates === null) return null
  for (const node of Object.values(updates as Record<string, unknown>)) {
    if (typeof node !== 'object' || node === null) continue
    const messages = (node as Record<string, unknown>).messages
    if (Array.isArray(messages)) {
      const result = extractPageResultFromMessages(messages)
      if (result) return result
    }
  }
  return null
}

export type { StateWithTasks }
