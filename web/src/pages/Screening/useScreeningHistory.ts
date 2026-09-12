import { useCallback, useState } from 'react'

const STORAGE_KEY = 'screening:history'
const MAX_HISTORY = 20

function loadHistory(): string[] {
  try {
    const parsed: unknown = JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? '[]')
    return Array.isArray(parsed)
      ? parsed.filter((item): item is string => typeof item === 'string')
      : []
  } catch {
    return []
  }
}

/** 最近问财问句历史（localStorage，最多 20 条，最新在前、去重）。 */
export function useScreeningHistory() {
  const [history, setHistory] = useState<string[]>(loadHistory)

  const persist = (next: string[]) => {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
    } catch {
      /* 存储不可用（隐私模式等）时仅保留会话内历史 */
    }
  }

  const add = useCallback((query: string) => {
    setHistory((prev) => {
      const next = [query, ...prev.filter((item) => item !== query)].slice(0, MAX_HISTORY)
      persist(next)
      return next
    })
  }, [])

  const clear = useCallback(() => {
    setHistory([])
    try {
      window.localStorage.removeItem(STORAGE_KEY)
    } catch {
      /* 同上 */
    }
  }, [])

  return { history, add, clear }
}
