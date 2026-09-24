"""AI 用量治理域内共享常量与 Redis 键模板（单一真相源）。"""

from typing import Any, Literal

UsageFeature = Literal["assistant", "page", "api_key", "system",
                       "kb_clean", "kb_extract", "kb_vision", "kb_embed"]
UsageOutlet = Literal["system", "byok"]

FEATURE_ASSISTANT: UsageFeature = "assistant"
FEATURE_PAGE: UsageFeature = "page"
FEATURE_API_KEY: UsageFeature = "api_key"
FEATURE_SYSTEM: UsageFeature = "system"

# F-KB 建库管线特征（系统维度，usage detail 携带 {sourceId, mediaId} 上下文）
FEATURE_KB_CLEAN: UsageFeature = "kb_clean"
FEATURE_KB_EXTRACT: UsageFeature = "kb_extract"
FEATURE_KB_VISION: UsageFeature = "kb_vision"
FEATURE_KB_EMBED: UsageFeature = "kb_embed"

OUTLET_SYSTEM: UsageOutlet = "system"
OUTLET_BYOK: UsageOutlet = "byok"

# BYOK 配置行的 provider 标识（user_token_usage.provider 与 ResolvedLLMConfig.provider）
BYOK_PROVIDER = "byok"

# 剩余额 Redis 镜像键（值为剩余 token 整数或哨兵 "inf" 表示不限额）
QUOTA_REMAIN_KEY_TEMPLATE = "quota:remain:{user_id}"
# 镜像 TTL 兜底：崩溃残留的未结算预扣到期后由 PG 重建吸收（宁紧勿超）
QUOTA_REMAIN_TTL_SECONDS = 7 * 86400
# Redis 值哨兵：不限额（豁免用户）
QUOTA_UNLIMITED_SENTINEL = "inf"

# system_setting 键（运行时可变全局设置）
SETTING_DEFAULT_QUOTA_TOKENS = "account.default_quota_tokens"
SETTING_PENDING_EXPIRE_DAYS = "account.pending_expire_days"
SETTING_ADMIN_EXEMPT = "quota.admin_exempt"

# 全局设置缺省值（迁移回填与读取兜底共用）
DEFAULT_SETTINGS: dict[str, Any] = {
    SETTING_DEFAULT_QUOTA_TOKENS: 100000,
    SETTING_PENDING_EXPIRE_DAYS: 30,
    SETTING_ADMIN_EXEMPT: True,
}

# 审计动作
AUDIT_REGISTER_APPROVE = "register.approve"
AUDIT_REGISTER_REJECT = "register.reject"
AUDIT_QUOTA_ADJUST = "quota.adjust"
AUDIT_SETTING_UPDATE = "account_setting.update"
