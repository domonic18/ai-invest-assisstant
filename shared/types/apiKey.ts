/** 个人 MCP 访问密钥（wire camelCase，对应后端 app/schemas/api_key.py）。 */

export interface ApiKey {
  id: number
  userId: number
  username: string | null
  name: string
  keyPrefix: string
  scopes: string[]
  expiresAt: string | null
  revokedAt: string | null
  lastUsedAt: string | null
  createdAt: string
}

export interface ApiKeyIssued extends ApiKey {
  /** 明文 token，仅签发响应返回一次 */
  token: string
  note: string
}

export interface ApiKeyCreateRequest {
  name: string
  expiresAt?: string | null
}

/** scope 展示文案（与后端 app/core/constants.py 的 API_KEY_SCOPES 对齐） */
export const API_KEY_SCOPE_LABELS: Record<string, string> = {
  'market:read': '行情只读',
  'trading:read': '交易只读',
  'kb:read': '知识库检索',
  'watchlist:read': '自选股只读',
  'watchlist:write': '自选股写入',
  'reports:read': '财报只读',
  'reports:collect': '财报补采',
}

export function apiKeyScopeLabel(scope: string): string {
  return API_KEY_SCOPE_LABELS[scope] ?? scope
}
