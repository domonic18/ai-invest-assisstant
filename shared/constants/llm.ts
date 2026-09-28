import type { LLMProtocol } from '../types/admin'

/** 渠道预置：选中供应商后自动填充 base_url 与协议（可手动覆盖）。 */
export interface LLMProviderPreset {
  label: string
  baseUrl: string
  protocol: LLMProtocol
  /** 国内主流厂商双协议端点不同（如 DeepSeek openai=`/` anthropic=`/anthropic`）：
   *  仅列与 baseUrl 不同的协议端点，其余协议回落 baseUrl。 */
  baseUrlByProtocol?: Partial<Record<LLMProtocol, string>>
}

export const LLM_PROVIDER_PRESETS: Record<string, LLMProviderPreset> = {
  deepseek: {
    label: 'DeepSeek',
    baseUrl: 'https://api.deepseek.com',
    protocol: 'openai',
    baseUrlByProtocol: { anthropic: 'https://api.deepseek.com/anthropic' },
  },
  zhipu: {
    label: '智谱 GLM',
    baseUrl: 'https://open.bigmodel.cn/api/paas/v4',
    protocol: 'openai',
    baseUrlByProtocol: { anthropic: 'https://open.bigmodel.cn/api/anthropic' },
  },
  // Kimi：baseUrl 为 Kimi For Coding 订阅端点（anthropic 形）；按量开放平台 openai 端点不同
  kimi: {
    label: 'Kimi',
    baseUrl: 'https://api.kimi.com/coding',
    protocol: 'anthropic',
    baseUrlByProtocol: { openai: 'https://api.moonshot.cn/v1' },
  },
  minimax: {
    label: 'MiniMax',
    baseUrl: 'https://api.minimaxi.com/v1',
    protocol: 'openai',
    baseUrlByProtocol: { anthropic: 'https://api.minimaxi.com/anthropic' },
  },
  openai: { label: 'OpenAI', baseUrl: 'https://api.openai.com/v1', protocol: 'openai' },
  anthropic: { label: 'Anthropic', baseUrl: 'https://api.anthropic.com', protocol: 'anthropic' },
  // 判断模型渠道（System One wire 协议，D23）：openrouter 为探针实证的生产 Jev 通道
  openrouter: { label: 'OpenRouter', baseUrl: 'https://openrouter.ai/api', protocol: 'systemone' },
  codiv: { label: 'Codiv', baseUrl: 'https://api.codiv.ai', protocol: 'systemone' },
}
