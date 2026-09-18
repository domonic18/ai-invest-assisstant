/** 任务配置页本地偏好：表格分类目录行的展开态（localStorage，损坏时回退默认全展开）。 */

const EXPANDED_KEY = 'tasks.expandedGroups'

function readJson<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : null
  } catch {
    return null
  }
}

function writeJson(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // 存储不可用时静默降级为会话内状态
  }
}

/** 当前展开的分类目录行 key 列表；从未设置过返回 null（由调用方决定默认值）。 */
export function getExpandedGroups(): string[] | null {
  const list = readJson<string[]>(EXPANDED_KEY)
  return Array.isArray(list) ? list : null
}

export function setExpandedGroups(keys: string[]): void {
  writeJson(EXPANDED_KEY, keys)
}
