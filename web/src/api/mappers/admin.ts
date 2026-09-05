import type {
  ApiAdminAiResultDetail,
  ApiAdminAiResultItem,
  ApiAdminAiSkillInfo,
  ApiAdminNewsResponse,
  ApiAdminReportResponse,
  ApiAdminStockResponse,
  ApiAdminTaskResponse,
  ApiAdminUserResponse,
  ApiCollectorChannelConfigResponse,
  ApiCollectorLogResponse,
  ApiCollectorTaskCatalogResponse,
  ApiDataTypeChannelsResponse,
  ApiLLMConfigResponse,
  ApiTrackedIndexResponse,
} from '@ai-invest/shared'
import type {
  AdminAiResultDetail,
  AdminAiResultItem,
  AdminAiSkillInfo,
  AdminNews,
  AdminReport,
  AdminStock,
  AdminTask,
  AdminUser,
  CollectorChannelConfig,
  CollectorDataTypeChannels,
  CollectorLog,
  CollectorTaskCatalog,
  LLMConfig,
  TrackedIndexConfig,
} from '@ai-invest/shared'

export function mapLLMConfig(dto: ApiLLMConfigResponse): LLMConfig {
  return {
    id: dto.id,
    name: dto.name,
    provider: dto.provider,
    baseUrl: dto.base_url,
    modelName: dto.model_name,
    apiKeyMasked: dto.api_key_masked,
    isDefault: dto.is_default,
    isActive: dto.is_active,
    extra: dto.extra,
    lastTestedAt: dto.last_tested_at,
    lastTestStatus: dto.last_test_status,
    lastTestError: dto.last_test_error,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  }
}

export function mapTrackedIndex(dto: ApiTrackedIndexResponse): TrackedIndexConfig {
  return {
    id: dto.id,
    indexCode: dto.index_code,
    indexName: dto.index_name,
    marketCategory: dto.market_category,
    dataSource: dto.data_source,
    sortOrder: dto.sort_order,
    isEnabled: dto.is_enabled,
    latestClose: dto.latest_close,
    latestChangePct: dto.latest_change_pct,
    latestTradeDate: dto.latest_trade_date,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  }
}

export function mapCollectorChannelConfig(dto: ApiCollectorChannelConfigResponse): CollectorChannelConfig {
  return {
    id: dto.id,
    source: dto.source,
    name: dto.name,
    baseUrl: dto.base_url,
    apiKeyMasked: dto.api_key_masked,
    isEnabled: dto.is_enabled,
    supportedDataTypes: dto.supported_data_types,
    extra: dto.extra,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  }
}

export function mapCollectorLog(dto: ApiCollectorLogResponse): CollectorLog {
  return {
    id: dto.id,
    taskName: dto.task_name,
    source: dto.source,
    status: dto.status,
    startedAt: dto.started_at,
    finishedAt: dto.finished_at,
    recordsCount: dto.records_count,
    errorMsg: dto.error_msg,
    metadata: dto.metadata,
  }
}

export function mapCollectorTaskCatalog(dto: ApiCollectorTaskCatalogResponse): CollectorTaskCatalog {
  return {
    items: dto.items.map((item) => ({
      name: item.name,
      label: item.label,
      dataType: item.data_type,
      sources: item.sources,
      configParams: item.config_params,
      runParams: item.run_params,
    })),
  }
}

export function mapCollectorDataTypeChannels(dto: ApiDataTypeChannelsResponse): CollectorDataTypeChannels {
  return {
    dataType: dto.data_type,
    channels: dto.channels.map((ch) => ({
      channelId: ch.channel_id,
      source: ch.source,
      name: ch.name,
      isEnabled: ch.is_enabled,
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
    isActive: dto.is_active,
    lastLoginAt: dto.last_login_at,
    createdAt: dto.created_at,
  }
}

export function mapAdminStock(dto: ApiAdminStockResponse): AdminStock {
  return {
    id: dto.id,
    stockCode: dto.stock_code,
    stockName: dto.stock_name,
    market: dto.market,
    industryL1: dto.industry_level_1,
    industryL2: dto.industry_level_2,
    industryL3: dto.industry_level_3,
    listingDate: dto.listing_date,
    totalShares: dto.total_shares,
    circulatingShares: dto.circulating_shares,
    fullName: dto.full_name,
    createdAt: dto.created_at,
  }
}

export function mapAdminReport(dto: ApiAdminReportResponse): AdminReport {
  return {
    id: dto.id,
    filePath: dto.file_path,
    originalName: dto.original_name,
    fileType: dto.file_type,
    stockCode: dto.stock_code,
    stockName: dto.stock_name,
    reportDate: dto.report_date,
    reportType: dto.report_type,
    broker: dto.broker,
    fileSize: dto.file_size,
    md5Hash: dto.md5_hash,
    downloadUrl: dto.download_url,
    downloadCount: dto.download_count,
    createdAt: dto.created_at,
  }
}

export function mapAdminNews(dto: ApiAdminNewsResponse): AdminNews {
  return {
    id: dto.id,
    stockCode: dto.stock_code,
    docType: dto.doc_type,
    title: dto.title,
    summary: dto.summary,
    content: dto.content,
    source: dto.source,
    sourceUrl: dto.source_url,
    publishDate: dto.publish_date,
    sentiment: dto.sentiment,
    keywords: dto.keywords,
    industryTags: dto.industry_tags,
    extra: dto.extra,
    createdAt: dto.created_at,
  }
}

export function mapAdminAiSkill(dto: ApiAdminAiSkillInfo): AdminAiSkillInfo {
  return {
    skillId: dto.skill_id,
    label: dto.label,
    eventType: dto.event_type,
  }
}

export function mapAdminAiResult(dto: ApiAdminAiResultItem): AdminAiResultItem {
  return {
    id: dto.id,
    skillId: dto.skill_id,
    keyFields: dto.key_fields.map((field) => ({ ...field })),
    model: dto.model,
    latencyMs: dto.latency_ms,
    status: dto.status,
    createdAt: dto.created_at,
    historyCount: dto.history_count,
    regeneratePrompt: dto.regenerate_prompt,
  }
}

export function mapAdminAiResultDetail(dto: ApiAdminAiResultDetail): AdminAiResultDetail {
  return {
    ...mapAdminAiResult(dto),
    errorMsg: dto.error_msg,
    structuredOutput: dto.structured_output,
  }
}

export function mapAdminTask(dto: ApiAdminTaskResponse): AdminTask {
  return {
    id: dto.id,
    taskName: dto.task_name,
    taskType: dto.task_type,
    source: dto.source,
    schedule: dto.schedule,
    isActive: dto.is_active,
    lastRunAt: dto.last_run_at,
    lastStatus: dto.last_status,
    lastError: dto.last_error,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  }
}
