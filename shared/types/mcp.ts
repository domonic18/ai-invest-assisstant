/** MCP 服务配置类型：camelCase wire，与后端 schemas/mcp_config.py 对齐。 */

/** 传输通道。 */
export type McpTransportType = 'stdio' | 'http' | 'sse'

export interface ApiMcpToolInfo {
  name: string
  description?: string | null
}

export interface ApiMcpServerConfig {
  id: number
  name: string
  transportType: McpTransportType
  command?: string | null
  args: string[]
  url?: string | null
  env: Record<string, string>
  headers: Record<string, string>
  enabled: boolean
  timeoutSeconds: number
  lastStatus?: 'ok' | 'failed' | null
  lastError?: string | null
  createdAt: string
  updatedAt: string
}

export interface ApiMcpServerCreateRequest {
  name: string
  transportType: McpTransportType
  command?: string | null
  args?: string[]
  url?: string | null
  env?: Record<string, string>
  headers?: Record<string, string>
  enabled?: boolean
  timeoutSeconds?: number
}

export interface ApiMcpServerUpdateRequest {
  name?: string
  transportType?: McpTransportType
  command?: string | null
  args?: string[] | null
  url?: string | null
  env?: Record<string, string> | null
  headers?: Record<string, string> | null
  enabled?: boolean
  timeoutSeconds?: number
}

/** 连接测试结果：成功带工具清单，失败带 error。 */
export interface ApiMcpServerTestResult {
  ok: boolean
  toolCount: number
  tools: ApiMcpToolInfo[]
  error?: string | null
}
