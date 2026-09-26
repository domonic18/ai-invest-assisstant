"""模拟盘 API 的 Pydantic schemas（camelCase wire，金额一律 float）。"""

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from app.schemas.base import CamelModel


class PaperTradeCashInfo(CamelModel):
    """资金概况（sidecar 实时透传）。"""

    nav: float | None = None
    available: float | None = None
    balance: float | None = None
    cum_inout: float | None = None
    last_inout: float | None = None


class PaperTradePositionRow(CamelModel):
    """持仓行（柜台字段以实抓为准，缺失项为 None，前端渲染 '-'）。"""

    symbol: str = ""
    stock_code: str = ""
    side: int | None = None
    volume: int | None = None
    available_volume: int | None = None
    avg_price: float | None = None
    last_price: float | None = None
    market_value: float | None = None
    profit: float | None = None
    profit_rate: float | None = None


class PaperTradeOrderRow(CamelModel):
    """委托行（本地表或 sidecar 未结委托）。"""

    cl_ord_id: str
    trade_date: date
    symbol: str
    stock_code: str
    side: int
    order_type: int
    position_effect: int
    price: float
    volume: int
    status: int
    order_source: str = "manual"
    ord_rej_reason: int | None = None
    ord_rej_reason_detail: str | None = None
    counter_created_at: datetime | None = None
    counter_updated_at: datetime | None = None


class PaperTradeExecutionRow(CamelModel):
    """成交回报行（本地表）。"""

    exec_id: str
    cl_ord_id: str
    trade_date: date
    symbol: str
    side: int | None = None
    exec_type: int | None = None
    price: float | None = None
    volume: int | None = None
    turnover: float | None = None
    commission: float | None = None
    counter_created_at: datetime | None = None


class PaperTradeOverviewResponse(CamelModel):
    """模拟盘总览：enabled=false 表示模拟盘功能未配置（前端展示引导卡）。"""

    enabled: bool = True
    cash: PaperTradeCashInfo | None = None
    positions: list[PaperTradePositionRow] = []
    unfinished_orders: list[PaperTradeOrderRow] = []


class PaperTradeNavPoint(CamelModel):
    """净值曲线单点。"""

    trade_date: date
    nav: float | None = None
    available: float | None = None


class PaperTradeNavResponse(CamelModel):
    """净值曲线（trade_date 升序）。"""

    items: list[PaperTradeNavPoint] = []


class PaperTradeOrderPageResponse(CamelModel):
    """委托分页（带业务日回显，前端标题展示）。"""

    total: int
    page: int
    page_size: int
    trade_date: date
    items: list[PaperTradeOrderRow] = []


class PaperTradeExecutionPageResponse(CamelModel):
    """成交回报分页（带业务日回显）。"""

    total: int
    page: int
    page_size: int
    trade_date: date
    items: list[PaperTradeExecutionRow] = []


class PaperTradeTradeMarkerRow(CamelModel):
    """B/S/T 图表标记单笔成交（当前用户全账户、按标的过滤，trade_date 升序）。"""

    trade_date: date
    counter_created_at: datetime | None = None
    side: str
    price: float | None = None
    volume: int | None = None


class PaperTradeTradeMarkerResponse(CamelModel):
    """B/S/T 图表标记成交列表。"""

    items: list[PaperTradeTradeMarkerRow] = []


# ============================================================
# 账户配置（多租户）
# ============================================================


class PaperTradeAccountRow(CamelModel):
    """账户配置行（token 只回掩码，明文不出库）。"""

    id: int
    name: str
    counter_account_id: str
    agent_key: str | None = None
    """归属交易 Agent；NULL = 用户账户。"""
    is_enabled: bool = True
    token_masked: str = ""
    last_error: str | None = None
    last_synced_at: datetime | None = None
    created_at: datetime | None = None


class PaperTradeAccountListResponse(CamelModel):
    """用户自有账户列表。"""

    items: list[PaperTradeAccountRow] = []


class PaperTradeAccountCreateRequest(CamelModel):
    """新增账户配置（掘金仿真 token + counter account_id）。"""

    name: str
    token: str
    counter_account_id: str


class PaperTradeAccountUpdateRequest(CamelModel):
    """更新账户配置（未提供的字段不变）。"""

    name: str | None = None
    token: str | None = None
    counter_account_id: str | None = None


class PaperTradePlaceOrderRequest(CamelModel):
    """人工下单请求（限价单必须带价格，柜台校验手数整数倍）。"""

    account_id: int
    """平台 6 位股票代码（或带柜台前缀完整代码，服务层按 stock_basic 主数据解析）。"""
    symbol: str
    side: str
    volume: int
    order_type: str = "limit"
    price: float = 0.0


class PaperTradeActionResponse(CamelModel):
    """下单/撤单动作结果。"""

    success: bool = True
    cl_ord_id: str = ""
    message: str = ""


class PaperTradeAccountSyncResponse(CamelModel):
    """单账户即时同步摘要（下单/撤单后调用）。"""

    trade_date: str
    account_id: int
    orders: int = 0
    executions: int = 0
    nav: float | None = None


# ============================================================
# 管理端
# ============================================================


class PaperTradeAdminAccountRow(PaperTradeAccountRow):
    """管理端账户行（附带归属用户）。"""

    user_id: int


class PaperTradeAdminAccountListResponse(CamelModel):
    """管理端全平台账户列表。"""

    items: list[PaperTradeAdminAccountRow] = []


# ============================================================
# 交易 Agent 注册表（Agent Hub 多 Agent 基座，agent-hub-plan.md D21）
# ============================================================


class TradingAgentProfileResponse(CamelModel):
    """交易 Agent 注册行视图：身份/介绍/模型绑定/风控/总闸/频率。"""

    agent_key: str
    name: str
    tagline: str
    strategy_desc: str
    style_desc: str
    llm_config_id: int | None = None
    methodology_source_id: int | None = None
    risk_max_position_pct: float
    risk_max_total_pct: float
    risk_max_daily_orders: int
    auto_exec_enabled: bool
    status: str
    plan_cadence: str = "daily"
    review_cadence: str = "daily"
    sort_order: int
    prompt_id: str
    accent_color: str
    updated_at: datetime | None = None


class TradingAgentListResponse(CamelModel):
    """交易 Agent 注册行列表（总览/下拉）。"""

    items: list[TradingAgentProfileResponse] = []


class AgentActivityItem(CamelModel):
    """总览近期活动条目（计划生成/触发、复盘生成）。"""

    kind: str
    title: str
    detail: str | None = None
    occurred_at: datetime | None = None


class AgentNextTask(CamelModel):
    """总览「接下来」条目：后端按 cron + 交易日历算好的下次触发时刻（UTC）。"""

    task: str
    scheduled_at: datetime


class AgentOverviewItem(CamelModel):
    """总览页单 Agent 聚合：介绍卡 + 模型 + 当日计数 + 近期活动 + 下次任务。"""

    profile: TradingAgentProfileResponse
    llm_name: str | None = None
    plan_count: int = 0
    selection_count: int = 0
    order_count: int = 0
    recent_activity: list[AgentActivityItem] = []
    next_tasks: list[AgentNextTask] = []


class AgentOverviewResponse(CamelModel):
    """总览页聚合载荷（/trading-agent/agents）。"""

    items: list[AgentOverviewItem] = []
    generated_at: datetime


class TradingAgentProfileUpdateRequest(CamelModel):
    """更新交易 Agent 注册信息（未提供的字段不变；任意状态可写，D28）。

    llm_config_id 空 = 平台默认 chat 模型，methodology_source_id 空 = 未启用
    方法论基座注入。status 开放 active/disabled 切换（停用 = 总览隐藏 + 不参与
    调度）；'planned' 仅为种子初始态，API 不可设置。身份字段（agent_key/
    prompt_id/sort_order）不开放更新。
    """

    name: str | None = None
    tagline: str | None = None
    strategy_desc: str | None = None
    style_desc: str | None = None
    llm_config_id: int | None = None
    methodology_source_id: int | None = None
    risk_max_position_pct: float | None = Field(default=None, ge=0, le=100)
    risk_max_total_pct: float | None = Field(default=None, ge=0, le=100)
    risk_max_daily_orders: int | None = Field(default=None, ge=1)
    auto_exec_enabled: bool | None = None
    accent_color: str | None = None
    status: Literal["active", "disabled"] | None = None
    plan_cadence: Literal["daily", "weekly", "monthly"] | None = None
    review_cadence: Literal["daily", "weekly", "monthly"] | None = None


# ============================================================
# 交易 Agent 复盘（批次 6）
# ============================================================


class TradingAgentTradeVerdictItem(CamelModel):
    """单笔委托三层判定。"""

    cl_ord_id: str
    stock_code: str
    selection_verdict: str
    plan_verdict: str
    execution_verdict: str
    reason: str


class TradingAgentReviewExperienceItem(CamelModel):
    """复盘提取经验条目。"""

    title: str
    body: str
    mem_type: str


class TradingAgentReviewResponse(CamelModel):
    """模拟盘分层复盘（ai_analysis_result.structured_output 契约镜像）。"""

    period: str
    trade_date: str
    overall: str
    trades: list[TradingAgentTradeVerdictItem] = []
    bias: str
    suggestion: str
    experiences: list[TradingAgentReviewExperienceItem] = []


class TradingAgentPlanResponse(CamelModel):
    """交易计划条目（「今日交易计划」区块与对话 list 工具共用）。"""

    id: int
    plan_date: date
    stock_code: str
    plan_type: str
    strategy: str
    buy_zone_low: float | None = None
    buy_zone_high: float | None = None
    target_price: float | None = None
    stop_loss: float
    position_pct: float
    status: str
    selection_id: int | None = None
    basis: str
    triggered_cl_ord_id: str | None = None


class TradingAgentPlansResponse(CamelModel):
    """指定日交易计划载荷：计划日 + 下一交易日（次日语义，D28）+ 计划列表。"""

    trade_date: date
    next_trade_date: date | None = None
    plans: list[TradingAgentPlanResponse] = []


class TradingAgentDatesResponse(CamelModel):
    """有记录日期清单（日历打点：计划日 + 各周期复盘基准日）。"""

    plan_dates: list[date] = []
    review_dates: dict[str, list[date]] = {}


class AgentSelectionItem(CamelModel):
    """agent 选股条目（模拟管理「Agent 自选」：AI 依据 + 置信度）。"""

    id: int
    stock_code: str
    reason: str
    confidence: float | None = None
    trade_date: date


class AgentWatchlistGroupResponse(CamelModel):
    """agent 自选分组（admin GET /trading-agent/selections；items 为当前 active 选股）。"""

    id: int
    name: str
    items: list[AgentSelectionItem] = []


class AgentMemoryResponse(CamelModel):
    """交易 Agent 记忆条目（方法论纪律 + 复盘沉淀）。"""

    id: int
    mem_type: str
    title: str
    body: str
    source: str
    status: str
    source_result_id: int | None = None
    created_at: datetime
    updated_at: datetime


class AgentMemoryUpdateRequest(CamelModel):
    """记忆编辑请求（未提供字段不变）。"""

    title: str | None = None
    body: str | None = None
    mem_type: Literal["discipline", "method", "lesson"] | None = None


class AgentMemoryStatusUpdateRequest(CamelModel):
    """记忆状态切换请求（archived 停用不删）。"""

    status: Literal["active", "archived"]
