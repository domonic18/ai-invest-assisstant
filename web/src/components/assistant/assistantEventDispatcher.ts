/**
 * 助手事件分派器（唯一入口）：custom 与 updates 双通道的事件全部经
 * dispatchCustomEvent / dispatchUpdates 收敛处理——注册表驱动、幂等，
 * Provider 与 runtimeAdapter 不再各自接线（防腐层的一部分）。
 */

import { useAssistantStore, type QuestionCard, type QuestionOption } from '@/stores/assistant'

import { parsePageEvent } from './pageEvents'
import { extractPageResult, extractQuestionFromUpdates, extractTodos } from './runtimeUtils'

/** ask_user SSE 事件 → 问题卡状态（宽松 parse：字段缺失/畸形不渲染） */
export function parseQuestionCard(event: unknown): QuestionCard | null {
  const e = event as { question?: unknown; options?: unknown; default?: unknown }
  const options = Array.isArray(e.options)
    ? e.options
        .map((raw) => {
          const opt = raw as { value?: unknown; label?: unknown }
          return { value: String(opt.value ?? ''), label: String(opt.label ?? '') } satisfies QuestionOption
        })
        .filter((opt) => opt.value && opt.label)
    : []
  const question = String(e.question ?? '')
  if (!question || options.length < 2) return null
  return {
    question,
    options,
    default: e.default == null ? null : String(e.default),
  }
}

/** 连续相同问题卡只生效一次（custom 与 updates 双通道送达同一标记时去重） */
let lastQuestionKey: string | null = null

function applyQuestion(marker: unknown): void {
  const card = parseQuestionCard(marker)
  if (!card) return
  const key = JSON.stringify(card)
  if (key === lastQuestionKey) return
  lastQuestionKey = key
  useAssistantStore.getState().setQuestionCard(card)
}

/** custom SSE 事件（回调签名 (eventType, data)：data 才是载荷，eventType 预留扩展）。 */
export function dispatchCustomEvent(_eventType: string, data: unknown): void {
  if (
    typeof data === 'object' &&
    data !== null &&
    (data as { type?: unknown }).type === 'question'
  ) {
    applyQuestion(data)
    return
  }
  const parsed = parsePageEvent(data)
  if (parsed) useAssistantStore.getState().setPageResult(parsed.result)
}

/** updates 通道载荷：todos / 页面回写事件 / 问题卡标记兜底提取。 */
export function dispatchUpdates(updates: unknown): void {
  const todos = extractTodos(updates)
  if (todos) useAssistantStore.getState().setTodos(todos)
  const pageResult = extractPageResult(updates)
  if (pageResult) useAssistantStore.getState().setPageResult(pageResult)
  const question = extractQuestionFromUpdates(updates)
  if (question) applyQuestion(question)
}
