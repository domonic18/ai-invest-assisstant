import type {
  ApiAdminAiResultDetail,
  ApiAdminAiResultItem,
  ApiAdminAiSkillInfo,
  ApiAdminNewsResponse,
  ApiAdminReportResponse,
  ApiAdminStockResponse,
  ApiAdminTaskResponse,
  ApiAdminTelegraphResponse,
  ApiAdminUserResponse,
  ApiCollectorChannelConfigResponse,
  ApiCollectorLogResponse,
  ApiCollectorTaskCatalogResponse,
  ApiDataTypeChannelsResponse,
  ApiLLMConfigResponse,
  ApiProxyConfigResponse,
} from '@ai-invest/shared'
import type {
  AdminAiResultDetail,
  AdminAiResultItem,
  AdminAiSkillInfo,
  AdminNews,
  AdminReport,
  AdminStock,
  AdminTask,
  AdminTelegraph,
  AdminUser,
  CollectorChannelConfig,
  CollectorDataTypeChannels,
  CollectorLog,
  CollectorTaskCatalog,
  LLMConfig,
  ProxyConfig,
} from '@ai-invest/shared'

export function mapLLMConfig(dto: ApiLLMConfigResponse): LLMConfig {
  return {
    id: dto.id,
    name: dto.name,
    provider: dto.provider,
    protocol: dto.protocol === 'anthropic' ? 'anthropic' : 'openai',
    baseUrl: dto.baseUrl,
    modelName: dto.modelName,
    apiKeyMasked: dto.apiKeyMasked,
    isDefault: dto.isDefault,
    isActive: dto.isActive,
    extra: dto.extra,
    lastTestedAt: dto.lastTestedAt,
    lastTestStatus: dto.lastTestStatus,
    lastTestError: dto.lastTestError,
    createdAt: dto.createdAt,
    updatedAt: dto.updatedAt,
  }
}


export function mapCollectorChannelConfig(dto: ApiCollectorChannelConfigResponse): CollectorChannelConfig {
  return {
    id: dto.id,
    source: dto.source,
    name: dto.name,
    baseUrl: dto.baseUrl,
    apiKeyMasked: dto.apiKeyMasked,
    isEnabled: dto.isEnabled,
    supportedDataTypes: dto.supportedDataTypes,
    extra: dto.extra,
    proxyConfigId: dto.proxyConfigId,
    createdAt: dto.createdAt,
    updatedAt: dto.updatedAt,
  }
}

export function mapProxyConfig(dto: ApiProxyConfigResponse): ProxyConfig {
  return {
    id: dto.id,
    name: dto.name,
    protocol: dto.protocol,
    host: dto.host,
    port: dto.port,
    username: dto.username,
    passwordMasked: dto.passwordMasked,
    isEnabled: dto.isEnabled,
    createdAt: dto.createdAt,
    updatedAt: dto.updatedAt,
  }
}

export function mapCollectorLog(dto: ApiCollectorLogResponse): CollectorLog {
  return {
    id: dto.id,
    taskName: dto.taskName,
    source: dto.source,
    status: dto.status,
    startedAt: dto.startedAt,
    finishedAt: dto.finishedAt,
    recordsCount: dto.recordsCount,
    errorMsg: dto.errorMsg,
    metadata: dto.metadata,
  }
}

export function mapCollectorTaskCatalog(dto: ApiCollectorTaskCatalogResponse): CollectorTaskCatalog {
  return {
    items: dto.items.map((item) => ({
      name: item.name,
      label: item.label,
      dataType: item.dataType,
      sources: item.sources,
      configParams: item.configParams,
      runParams: item.runParams,
    })),
  }
}

export function mapCollectorDataTypeChannels(dto: ApiDataTypeChannelsResponse): CollectorDataTypeChannels {
  return {
    dataType: dto.dataType,
    channels: dto.channels.map((ch) => ({
      channelId: ch.channelId,
      source: ch.source,
      name: ch.name,
      isEnabled: ch.isEnabled,
      priority: ch.priority,
    })),
  }
}

export function mapAdminUser(dto: ApiAdminUserResponse): AdminUser {
  return {
    id: dto.id,
    username: dto.username,
    email: dto.email,
    role: dto.role,
    isActive: dto.isActive,
    lastLoginAt: dto.lastLoginAt,
    createdAt: dto.createdAt,
  }
}

export function mapAdminStock(dto: ApiAdminStockResponse): AdminStock {
  return {
    id: dto.id,
    stockCode: dto.stockCode,
    stockName: dto.stockName,
    market: dto.market,
    industryL1: dto.industryLevel1,
    industryL2: dto.industryLevel2,
    industryL3: dto.industryLevel3,
    listingDate: dto.listingDate,
    totalShares: dto.totalShares,
    circulatingShares: dto.circulatingShares,
    fullName: dto.fullName,
    createdAt: dto.createdAt,
  }
}

export function mapAdminReport(dto: ApiAdminReportResponse): AdminReport {
  return {
    id: dto.id,
    filePath: dto.filePath,
    originalName: dto.originalName,
    fileType: dto.fileType,
    stockCode: dto.stockCode,
    stockName: dto.stockName,
    reportDate: dto.reportDate,
    reportType: dto.reportType,
    broker: dto.broker,
    fileSize: dto.fileSize,
    md5Hash: dto.md5Hash,
    downloadUrl: dto.downloadUrl,
    downloadCount: dto.downloadCount,
    createdAt: dto.createdAt,
  }
}

export function mapAdminNews(dto: ApiAdminNewsResponse): AdminNews {
  return {
    id: dto.id,
    stockCode: dto.stockCode,
    docType: dto.docType,
    title: dto.title,
    summary: dto.summary,
    content: dto.content,
    source: dto.source,
    sourceUrl: dto.sourceUrl,
    publishDate: dto.publishDate,
    sentiment: dto.sentiment,
    keywords: dto.keywords,
    industryTags: dto.industryTags,
    extra: dto.extra,
    createdAt: dto.createdAt,
  }
}

export function mapAdminAiSkill(dto: ApiAdminAiSkillInfo): AdminAiSkillInfo {
  return {
    skillId: dto.skillId,
    label: dto.label,
    eventType: dto.eventType,
  }
}

export function mapAdminAiResult(dto: ApiAdminAiResultItem): AdminAiResultItem {
  return {
    id: dto.id,
    skillId: dto.skillId,
    keyFields: dto.keyFields.map((field) => ({ ...field })),
    model: dto.model,
    latencyMs: dto.latencyMs,
    status: dto.status,
    createdAt: dto.createdAt,
    historyCount: dto.historyCount,
    regeneratePrompt: dto.regeneratePrompt,
  }
}

export function mapAdminAiResultDetail(dto: ApiAdminAiResultDetail): AdminAiResultDetail {
  return {
    ...mapAdminAiResult(dto),
    errorMsg: dto.errorMsg,
    structuredOutput: dto.structuredOutput,
  }
}

export function mapAdminTelegraph(dto: ApiAdminTelegraphResponse): AdminTelegraph {
  return {
    id: dto.id,
    title: dto.title,
    content: dto.content,
    category: dto.category,
    importance: dto.importance,
    stockCodes: dto.stockCodes,
    publishTime: dto.publishTime,
    aiScore: dto.aiScore,
    aiScoredAt: dto.aiScoredAt,
  }
}

export function mapAdminTask(dto: ApiAdminTaskResponse): AdminTask {
  return {
    id: dto.id,
    taskName: dto.taskName,
    taskType: dto.taskType,
    source: dto.source,
    schedule: dto.schedule,
    isActive: dto.isActive,
    lastRunAt: dto.lastRunAt,
    lastStatus: dto.lastStatus,
    lastError: dto.lastError,
    createdAt: dto.createdAt,
    updatedAt: dto.updatedAt,
  }
}
