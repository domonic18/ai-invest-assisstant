/**
 * 详情页 agentKey 上下文：路由参数单点下发，各面板经 useAgentKey() 取键，
 * 免去逐层 props 钻取（面板同时被 Tabs 与工作台侧栏复用）。
 * Provider JSX 在 TradingAgent 页内（本文件保持 .ts 以满足 fast-refresh 纪律）。
 */
import { createContext, useContext } from 'react'

export const AgentKeyContext = createContext<string>('short-line')

/** 当前详情页的 Agent 键（未包 Provider 时回落短线默认 Agent）。 */
export function useAgentKey(): string {
  return useContext(AgentKeyContext)
}
