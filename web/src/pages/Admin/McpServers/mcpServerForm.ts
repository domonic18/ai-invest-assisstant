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
