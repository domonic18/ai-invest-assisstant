import type { PageAssistantResult, TodoStep } from '@/stores/assistant'

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

/** 从 messages 列表或 updates 中提取产业链分析完成事件。 */
export function extractPageResultFromMessages(messages: unknown[]): PageAssistantResult | null {
  for (const msg of messages) {
    if (typeof msg !== 'object' || msg === null) continue
    const typed = msg as Record<string, unknown>
    if (typed.type !== 'tool') continue
    const content = typed.content
    if (typeof content !== 'object' || content === null) continue
    const event = (content as Record<string, unknown>).__event__
    if (typeof event !== 'object' || event === null) continue
    const e = event as Record<string, unknown>
    if (e.type !== 'industry_chain.analysis_complete') continue
    return {
      type: 'industry_chain.analysis_complete',
      industry: String(e.industry ?? ''),
      versionId: Number(e.version_id),
      versionNo: Number(e.version_no),
      createdAt: e.created_at ? String(e.created_at) : undefined,
    }
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
