import { LLM_PROVIDER_PRESETS } from '@ai-invest/shared'
import type { LLMProtocol, LLMProviderPreset, LlmPurpose } from '@ai-invest/shared'

/** chat/vision 场景按供应商预设推断协议；systemone 渠道预设（openrouter/codiv）
 *  跑对话时走其 OpenAI 兼容端点。 */
export function chatProtocolForProvider(provider: string): LLMProtocol {
  const preset = LLM_PROVIDER_PRESETS[provider]
  return preset && preset.protocol !== 'systemone' ? preset.protocol : 'openai'
}

/** 用途 → 协议派生（与后端 normalize_purpose_protocol 同一对偶规则）：
 *  decision 恒 systemone、embedding 恒 openai（嵌入端点为 OpenAI 形状）；
 *  chat/vision 保留现值，仅当现值不合法（从 decision 带来的 systemone）时按供应商回落。 */
export function protocolForPurpose(
  purpose: LlmPurpose,
  provider: string,
  current: LLMProtocol,
): LLMProtocol {
  if (purpose === 'decision') return 'systemone'
  if (purpose === 'embedding') return 'openai'
  return current === 'systemone' ? chatProtocolForProvider(provider) : current
}

/** 供应商预设 × 协议 → 默认端点：协议专有端点优先，其余回落预设 baseUrl。 */
export function resolvePresetBaseUrl(preset: LLMProviderPreset, protocol: LLMProtocol): string {
  return preset.baseUrlByProtocol?.[protocol] ?? preset.baseUrl
}
