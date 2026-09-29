"""模拟盘 API 的 Pydantic schemas（camelCase wire，金额一律 float）。"""

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from app.schemas.base import CamelModel
from app.schemas.skill import SkillFile


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
    cum_inout: float | None = None


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

#: 盘中自主执行三态（D21，批次 8）：off 停用 / shadow 判断不下单 / active 真实执行
IntradayExecMode = Literal["off", "shadow", "active"]


class TradingAgentProfileResponse(CamelModel):
    """交易 Agent 注册行视图：身份/介绍/模型绑定/风控/总闸/频率。"""

    agent_key: str
    name: str
    tagline: str
    llm_config_id: int | None = None
    methodology_source_id: int | None = None
    risk_max_position_pct: float
    risk_max_total_pct: float
    risk_max_daily_orders: int
    #: 盘中自主执行三态（D21，批次 8）
    intraday_exec_mode: IntradayExecMode
    #: 盘中执行人工暂停（true = tick/尾盘强检短路，计划/复盘不受影响）
    intraday_paused: bool = False
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
    stock_code: str | None = None
    stock_name: str | None = None
    occurred_at: datetime | None = None


class AgentNextTask(CamelModel):
    """总览「接下来」条目：后端按 cron + 交易日历算好的下次触发时刻（UTC）。"""

    task: str
    scheduled_at: datetime


AgentRuntimeState = Literal["working", "produced_today", "idle", "paused", "off"]


class AgentOverviewItem(CamelModel):
    """总览页单 Agent 聚合：介绍卡 + 模型 + 当日计数 + 近期活动 + 下次任务。

    runtime_state（D32）：working=collector_log 运行中且 cadence 今日命中；
    produced_today=当日已产出计划/复盘；idle=待命；off=未启用（占位）。
    """

    profile: TradingAgentProfileResponse
    llm_name: str | None = None
    runtime_state: AgentRuntimeState = "off"
    state_label: str | None = None
    account_name: str | None = None
    plan_count: int = 0
    selection_count: int = 0
    order_count: int = 0
    recent_activity: list[AgentActivityItem] = []
    next_tasks: list[AgentNextTask] = []


class AgentOverviewResponse(CamelModel):
    """总览页聚合载荷（/trading-agent/agents）。"""

    items: list[AgentOverviewItem] = []
    generated_at: datetime


class TradingAgentCreateRequest(CamelModel):
    """新建交易 Agent（D29：注册表开放 CRUD，创建即 active 参与调度）。

    技能目录与人设 YAML 均可不建——计划技能走 trading-default 共享兜底，
    prompt_id 指向任意既有模板即可。
    """

    agent_key: str = Field(min_length=2, max_length=32)
    name: str = Field(min_length=1, max_length=64)
    tagline: str | None = Field(default=None, max_length=128)
    prompt_id: str = Field(min_length=1, max_length=64)
    accent_color: str | None = Field(default=None, max_length=16)
    plan_cadence: Literal["daily", "weekly", "monthly"] | None = None
    review_cadence: Literal["daily", "weekly", "monthly"] | None = None
    llm_config_id: int | None = None
    methodology_source_id: int | None = None


class TradingAgentPromptTemplate(CamelModel):
    """可用会话人设模板（prompts/agents/trading_agent_*.yaml 扫描）。"""

    prompt_id: str
    label: str


class AgentAutomationTask(CamelModel):
    """Agent 自动化任务视图（cron + 状态 + 下次/最近执行）。"""

    key: str
    label: str
    cron: str | None = None
    task_active: bool = False
    cadence: Literal["daily", "weekly", "monthly"] | None = None
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    last_status: str | None = None


class AgentMemoryCounts(CamelModel):
    """Agent 活跃记忆按类型计数（能力视图消费）。"""

    discipline: int = 0
    method: int = 0
    lesson: int = 0
    active_total: int = 0


class AgentCapabilityResponse(CamelModel):
    """Agent 能力/状态视图（详情页工作台右栏，D29）。

    一屏回答「agent 靠什么工作」：人设 + 方法论知识源（趋势理论等 KB 源）
    + 作业技能（选股→交易→复盘程序）+ 模型 + 活跃记忆 + 自动化任务与近期活动。
    """

    profile: TradingAgentProfileResponse
    llm_name: str | None = None
    methodology_source_name: str | None = None
    skill_id: str
    skill_label: str
    skill_is_shared_default: bool = False
    memory_counts: AgentMemoryCounts = AgentMemoryCounts()
    automation: list[AgentAutomationTask] = []
    recent_activity: list[AgentActivityItem] = []


class TradingAgentPromptContent(CamelModel):
    """会话人设 YAML 原文（配置页只读浏览，D30）。"""

    prompt_id: str
    label: str
    content: str


class AgentMethodologyDiscipline(CamelModel):
    """方法论纪律条目（KB published，全量展示）。"""

    title: str
    body: str


class AgentMethodologyPoint(CamelModel):
    """方法论知识卡片条目（method/theorem/concept/case）。"""

    title: str
    point_type: str
    body: str


class AgentMethodologyView(CamelModel):
    """方法论基座可视化载荷（配置页只读；未绑定源为 null，D30）。"""

    source_id: int
    source_name: str
    outline: str
    disciplines: list[AgentMethodologyDiscipline] = []
    points: list[AgentMethodologyPoint] = []


class AgentSkillFilesResponse(CamelModel):
    """Agent 作业技能包可视化载荷（配置页「作业技能」区，D30）。

    trading 技能不进 skill 表（广场不可见），本端点直读镜像 ``skills/<id>/``
    目录返回文件清单；``skill_is_shared_default`` 提示共享兜底（专属目录未建）。
    """

    skill_id: str
    skill_label: str
    skill_is_shared_default: bool = False
    files: list[SkillFile] = []
    methodology: AgentMethodologyView | None = None


class TradingAgentProfileUpdateRequest(CamelModel):
    """更新交易 Agent 注册信息（未提供的字段不变；任意状态可写，D28）。

    llm_config_id 空 = 平台默认 chat 模型，methodology_source_id 空 = 未启用
    方法论基座注入。status 开放 active/disabled 切换（停用 = 总览隐藏 + 不参与
    调度）；'planned' 仅为种子初始态，API 不可设置。prompt_id 开放换绑（D30，
    须在模板清单内）；agent_key/sort_order 不开放更新。
    """

    name: str | None = None
    tagline: str | None = None
    prompt_id: str | None = None
    llm_config_id: int | None = None
    methodology_source_id: int | None = None
    risk_max_position_pct: float | None = Field(default=None, ge=0, le=100)
    risk_max_total_pct: float | None = Field(default=None, ge=0, le=100)
    risk_max_daily_orders: int | None = Field(default=None, ge=1)
    #: 盘中自主执行三态（D21，批次 8）
    intraday_exec_mode: IntradayExecMode | None = None
    #: 盘中执行人工暂停开关（true = 冻结 tick/尾盘强检）
    intraday_paused: bool | None = None
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


class TradingAgentMethodologyCheckItem(CamelModel):
    """单条方法论纪律验证结论（D34：KB 纪律逐条 followed/violated/not_applicable）。"""

    title: str
    verdict: str
    note: str


class TradingAgentReviewResponse(CamelModel):
    """模拟盘分层复盘（ai_analysis_result.structured_output 契约镜像）。

    ``noTargetReason`` 非空 = 已执行但无复盘对象（空仓），前端与「未生成」区分。"""

    period: str
    trade_date: str
    overall: str
    trades: list[TradingAgentTradeVerdictItem] = []
    bias: str
    suggestion: str
    market_context: str = ""
    methodology_check: list[TradingAgentMethodologyCheckItem] = []
    experiences: list[TradingAgentReviewExperienceItem] = []
    no_target_reason: str | None = None


class TradingAgentPlanResponse(CamelModel):
    """交易计划条目（「今日交易计划」区块与对话 list 工具共用）。"""

    id: int
    plan_date: date
    stock_code: str
    stock_name: str | None = None
    plan_type: str
    strategy: str
    buy_zone_low: float | None = None
    buy_zone_high: float | None = None
    target_price: float | None = None
    stop_loss: float
    position_pct: float
    status: str
    selection_id: int | None = None
    held_volume: int | None = None
    """截至计划日按成交聚合的持仓股数（未绑定账户/无成交为 None）。"""
    basis: str
    triggered_cl_ord_id: str | None = None


class TradingAgentPlansResponse(CamelModel):
    """指定日交易计划载荷：计划日 + 下一交易日（次日语义，D28）+ 计划列表。

    ``stand_aside_reason`` 供前端三态区分：plans 非空为计划列表；plans 空
    且原因非空 = 已生成·空仓观望；plans 空且原因为 null = 该日未生成。
    """

    trade_date: date
    next_trade_date: date | None = None
    plans: list[TradingAgentPlanResponse] = []
    stand_aside_reason: str | None = None


class TradingAgentDatesResponse(CamelModel):
    """有记录日期清单（日历打点：计划日 + 各周期复盘基准日）。"""

    plan_dates: list[date] = []
    review_dates: dict[str, list[date]] = {}


# ============================================================
# 交易 Agent 盘中执行观测（批次 8 PR-3：执行动态 Tab 数据面）
# ============================================================


class TradingAgentObservationDecision(CamelModel):
    """单行观测的判断上下文（服务端解析 JSONB 产物，键缺失为 None）。"""

    #: L1 served model 版本（判断主备切换时区分实际应答臂）
    served_model: str | None = None
    #: Choice 答案选中项（execute_now/wait_pullback/give_up）
    choice: str | None = None
    confidence: float | None = None
    #: Noul 答案（分时形态/止损有效性，布尔）
    noul: bool | None = None
    #: Score 答案（盘面支持度 1-5）
    score: float | None = None
    #: 观测窗口标记；'tail_check' = 尾盘强检行（plan_id 恒空）
    window: str | None = None


class TradingAgentObservationItem(CamelModel):
    """盘中执行观测条目（执行动态 Tab 行卡片，一次 tick 对一个标的的判定）。"""

    id: int
    tick_time: datetime
    trade_date: date
    agent_key: str
    plan_id: int | None = None
    stock_code: str
    stock_name: str | None = None
    plan_type: str | None = None
    price: float | None = None
    change_pct: float | None = None
    l0_verdict: str
    trigger_reason: str | None = None
    #: L0 比价细节文案（心跳/拒绝行的人话原因；触发行通常为 None）
    l0_detail: str | None = None
    decision: TradingAgentObservationDecision | None = None
    #: no_action 行无动作（None）；execute/wait/abandon/suppress
    action: str | None = None
    suppression_reason: str | None = None
    is_shadow: bool = True
    cl_ord_id: str | None = None
    order_volume: int | None = None


class TradingAgentObservationSummary(CamelModel):
    """全天口径计数（不受 significant 过滤影响，顶部统计条数据源）。"""

    total_ticks: int = 0
    significant_ticks: int = 0
    l0_verdict_counts: dict[str, int] = {}
    action_counts: dict[str, int] = {}
    suppression_counts: dict[str, int] = {}


class TradingAgentObservationPage(CamelModel):
    """执行观测分页载荷（items 按 significant 过滤，summary 恒全天口径）。"""

    trade_date: date
    total: int
    page: int
    page_size: int
    items: list[TradingAgentObservationItem] = []
    summary: TradingAgentObservationSummary = Field(
        default_factory=TradingAgentObservationSummary
    )


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


class AgentMemoryCreateRequest(CamelModel):
    """手动沉淀记忆请求（source='manual'，立即 active 注入次日计划）。"""

    title: str = Field(max_length=128)
    body: str
    mem_type: Literal["discipline", "method", "lesson"]


class AgentMemoryUpdateRequest(CamelModel):
    """记忆编辑请求（未提供字段不变）。"""

    title: str | None = None
    body: str | None = None
    mem_type: Literal["discipline", "method", "lesson"] | None = None


class AgentMemoryStatusUpdateRequest(CamelModel):
    """记忆状态切换请求（archived 停用不删）。"""

    status: Literal["active", "archived"]
