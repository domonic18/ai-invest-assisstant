import type { AsrProtocol } from '../types/admin'

/** ASR 渠道预置：选中供应商后自动填充 base_url/model 与协议（自定义可覆盖）。 */
export interface AsrProviderPreset {
  label: string
  baseUrl: string
  model: string
  protocol: AsrProtocol
}

export const ASR_PROVIDER_PRESETS: Record<string, AsrProviderPreset> = {
  // MiniMax 走专有 /v1/speech_to_text 协议
  minimax: {
    label: 'MiniMax',
    baseUrl: 'https://api.minimaxi.com',
    model: 'asr-1.0',
    protocol: 'minimax',
  },
  // 以下走 OpenAI 兼容转写协议（POST /v1/audio/transcriptions，whisper 事实标准）
  siliconflow: {
    label: '硅基流动',
    baseUrl: 'https://api.siliconflow.cn/v1',
    model: 'FunAudioLLM/SenseVoiceSmall',
    protocol: 'openai',
  },
  groq: {
    label: 'Groq',
    baseUrl: 'https://api.groq.com/openai/v1',
    model: 'whisper-large-v3',
    protocol: 'openai',
  },
  openai: {
    label: 'OpenAI',
    baseUrl: 'https://api.openai.com/v1',
    model: 'whisper-1',
    protocol: 'openai',
  },
}
