import type { LLMProtocol } from '../types/admin'

/** 渠道预置：选中供应商后自动填充 base_url 与协议（可手动覆盖）。 */
export interface LLMProviderPreset {
  label: string
  baseUrl: string
  protocol: LLMProtocol
}

export const LLM_PROVIDER_PRESETS: Record<string, LLMProviderPreset> = {
  deepseek: { label: 'DeepSeek', baseUrl: 'https://api.deepseek.com', protocol: 'openai' },
  zhipu: { label: '智谱 GLM', baseUrl: 'https://open.bigmodel.cn/api/paas/v4', protocol: 'openai' },
  kimi: { label: 'Kimi', baseUrl: 'https://api.kimi.com/coding', protocol: 'anthropic' },
  minimax: { label: 'MiniMax', baseUrl: 'https://api.minimaxi.com/v1', protocol: 'openai' },
  openai: { label: 'OpenAI', baseUrl: 'https://api.openai.com/v1', protocol: 'openai' },
  anthropic: { label: 'Anthropic', baseUrl: 'https://api.anthropic.com', protocol: 'anthropic' },
}
