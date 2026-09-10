import type { McpTransportType } from '@ai-invest/shared'

export interface McpServerFormValues {
  name: string
  transportType: McpTransportType
  command?: string
  args?: string
  url?: string
  headers?: { key: string; value: string }[]
  env?: { key: string; value: string }[]
  enabled: boolean
  timeoutSeconds: number
}

export interface McpServerPayload {
  name: string
  transportType: McpTransportType
  command: string | null
  args: string[]
  url: string | null
  env: Record<string, string>
  headers: Record<string, string>
  enabled: boolean
  timeoutSeconds: number
}

function toRecord(pairs: { key: string; value: string }[] | undefined): Record<string, string> {
  return Object.fromEntries(
    (pairs ?? []).filter((p) => p.key.trim() !== '').map((p) => [p.key.trim(), p.value]),
  )
}

export interface McpImportedConfig {
  name?: string
  transportType: McpTransportType
  command?: string
  args: string[]
  url?: string
  env: Record<string, string>
  headers: Record<string, string>
}

/** 解析行业标准 mcpServers JSON 配置（Claude Desktop / Cursor 形状），取第一个 server。 */
export function parseMcpConfigJson(text: string): McpImportedConfig {
  const trimmed = text.trim()
  if (!trimmed) throw new Error('请粘贴 JSON 配置内容')
  let parsed: unknown
  try {
    parsed = JSON.parse(trimmed)
  } catch {
    throw new Error('不是合法的 JSON')
  }
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    throw new Error('JSON 顶层须为对象')
  }
  const root = parsed as Record<string, unknown>
  const servers = root.mcpServers as Record<string, unknown> | undefined
  let name: string | undefined
  let cfg: Record<string, unknown>
  if (servers && typeof servers === 'object' && !Array.isArray(servers)) {
    const entries = Object.entries(servers)
    if (entries.length === 0) throw new Error('mcpServers 为空')
    const [firstName, firstCfg] = entries[0]
    if (typeof firstCfg !== 'object' || firstCfg === null) {
      throw new Error(`mcpServers.${firstName} 不是对象`)
    }
    name = firstName
    cfg = firstCfg as Record<string, unknown>
  } else {
    cfg = root
  }

  const url = typeof cfg.url === 'string' && cfg.url.trim() ? cfg.url.trim() : undefined
  const command =
    typeof cfg.command === 'string' && cfg.command.trim() ? cfg.command.trim() : undefined
  const declared =
    typeof cfg.type === 'string' ? cfg.type : typeof cfg.transport === 'string' ? cfg.transport : ''
  let transportType: McpTransportType
  if (declared === 'sse' || declared === 'http' || declared === 'stdio') {
    transportType = declared
  } else if (url && !command) {
    transportType = 'http'
  } else if (command && !url) {
    transportType = 'stdio'
  } else {
    throw new Error('配置缺少 url 或 command，无法判断传输通道')
  }

  const args = Array.isArray(cfg.args)
    ? cfg.args.map((a) => String(a))
    : typeof cfg.args === 'string' && cfg.args.trim()
      ? cfg.args.trim().split(/\s+/)
      : []
  const toStrRecord = (value: unknown): Record<string, string> => {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return {}
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([k, v]) => [k, String(v)]),
    )
  }
  return {
    ...(name !== undefined ? { name } : {}),
    transportType,
    ...(command !== undefined ? { command } : {}),
    args,
    ...(url !== undefined ? { url } : {}),
    env: toStrRecord(cfg.env),
    headers: toStrRecord(cfg.headers),
  }
}

/** 表单值 → 后端 create/update payload（按 transport 清空无关字段）。 */
export function toPayload(values: McpServerFormValues): McpServerPayload {
  const isStdio = values.transportType === 'stdio'
  return {
    name: values.name.trim(),
    transportType: values.transportType,
    command: isStdio ? values.command?.trim() || null : null,
    args: isStdio
      ? (values.args ?? '')
          .split('\n')
          .map((line) => line.trim())
          .filter(Boolean)
      : [],
    url: isStdio ? null : values.url?.trim() || null,
    env: isStdio ? toRecord(values.env) : {},
    headers: isStdio ? {} : toRecord(values.headers),
    enabled: values.enabled,
    timeoutSeconds: values.timeoutSeconds,
  }
}
