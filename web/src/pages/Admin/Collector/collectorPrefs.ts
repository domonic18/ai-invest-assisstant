/** 执行页本地偏好：常用任务（最近触发）与目录分组折叠态。 */

const FREQ_KEY = 'collector.frequentTasks'
/** v2：分组键从 dataType 换为业务分类，旧键作废。 */
const COLLAPSED_KEY = 'collector.collapsedGroups.v2'
const FREQ_CAP = 5

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

/** 最近触发的任务名（最新在前，上限 5）。 */
export function getFrequentTasks(): string[] {
  const list = readJson<string[]>(FREQ_KEY)
  return Array.isArray(list) ? list.slice(0, FREQ_CAP) : []
}

/** 触发成功后记录：去重置顶，超出上限截断。 */
export function pushFrequentTask(taskName: string): void {
  const next = [taskName, ...getFrequentTasks().filter((t) => t !== taskName)]
  writeJson(FREQ_KEY, next.slice(0, FREQ_CAP))
}

/** 当前折叠的数据类型分组 key 列表；从未设置过返回 null（由调用方决定默认值）。 */
export function getCollapsedGroups(): string[] | null {
  const list = readJson<string[]>(COLLAPSED_KEY)
  return Array.isArray(list) ? list : null
}

export function setCollapsedGroups(keys: string[]): void {
  writeJson(COLLAPSED_KEY, keys)
}
