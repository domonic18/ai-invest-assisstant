/**
 * 详情页 agentKey 上下文：路由参数单点下发，各面板经 useAgentKey() 取键，
 * 免去逐层 props 钻取（面板同时被 Tabs 与工作台侧栏复用）。
 * Provider JSX 在 TradingAgent 页内（本文件保持 .ts 以满足 fast-refresh 纪律）。
 */
import { createContext, useContext } from 'react'

/** 详情页 agentKey 上下文：Provider 必传（TradingAgent 页内路由参数注入）。 */
export const AgentKeyContext = createContext<string | null>(null)

/** 当前详情页的 Agent 键。 */
export function useAgentKey(): string {
  const agentKey = useContext(AgentKeyContext)
  if (!agentKey) {
    throw new Error('useAgentKey 必须在 AgentKeyContext.Provider 内使用')
  }
  return agentKey
}
