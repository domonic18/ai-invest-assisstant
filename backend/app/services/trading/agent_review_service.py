"""模拟盘分层复盘服务门面（稳定入口；实现按职责拆分在同包模块）。

- ``agent_review_window``：窗口入参统一校验 + 交易日历收边 + 派发前预检
- ``agent_review_queries``：已生成复盘读取、跨窗口对比、日历打点日期
- ``agent_review_generate``：生成编排（取数 → LLM → 校验 → 落库 → 经验沉淀）
- ``agent_review_llm``：prompt 装配、结构化生成与幻觉委托剔除
- ``agent_review_cache``：缓存键与 ``ai_analysis_result`` 读写
- ``agent_review_periods``：六档周期窗口模型与周期末判定

本模块只做再导出，四个入口（Admin API / service / collector / Agent 工具）
继续按原名字调用，避免实现拆分破坏调用面。
"""

from app.services.trading.agent_review_cache import (
    input_hash,
    load_cached,
    persist_review,
)
from app.services.trading.agent_review_content import (
    REVIEW_SKILL_ID,
    PaperTradeReviewRecord,
    ReviewGenerateResult,
)
from app.services.trading.agent_review_errors import (
    PaperTradeReviewLockedError,
    ReviewWindowNotReadyError,
    TradingReviewNotFoundError,
)
from app.services.trading.agent_review_generate import generate_review
from app.services.trading.agent_review_llm import review_prompt_skill_id
from app.services.trading.agent_review_periods import (
    ReviewPeriod,
    ReviewWindow,
    is_last_trading_day_of_month,
    is_last_trading_day_of_week,
)
from app.services.trading.agent_review_queries import (
    ReviewCompareResult,
    compare_reviews,
    get_review,
    list_review_dates,
)
from app.services.trading.agent_review_window import (
    ReviewWindowRequest,
    ReviewWindowScope,
    ensure_window_ready,
    resolve_requested_window,
    resolve_window,
    sync_pending_message,
)

__all__ = [
    "PaperTradeReviewLockedError",
    "PaperTradeReviewRecord",
    "REVIEW_SKILL_ID",
    "ReviewCompareResult",
    "ReviewGenerateResult",
    "ReviewPeriod",
    "ReviewWindow",
    "ReviewWindowNotReadyError",
    "ReviewWindowRequest",
    "ReviewWindowScope",
    "TradingReviewNotFoundError",
    "compare_reviews",
    "ensure_window_ready",
    "generate_review",
    "get_review",
    "input_hash",
    "is_last_trading_day_of_month",
    "is_last_trading_day_of_week",
    "list_review_dates",
    "load_cached",
    "persist_review",
    "resolve_requested_window",
    "resolve_window",
    "review_prompt_skill_id",
    "sync_pending_message",
]
