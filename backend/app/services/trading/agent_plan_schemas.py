"""每日计划 LLM 契约类型（结构化输出 schema + 生成结果）。

独立成模块以便 ``agent_plan_service``（编排）/ ``agent_plan_input``（输入
组装）/ ``agent_plan_persist``（落库）三方共享，避免相互依赖。结构化输出
字段全 required（禁默认值铁律：带默认值不进 JSON Schema required，LLM 会
静默省略）。
"""

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, field_validator


class PlanSelectionItem(BaseModel):
    """选股条目（字段禁默认值——LLM 必须对每项显式表态）。"""

    stock_code: str
    reason: str
    confidence: float | None


class PlanTradePlanItem(BaseModel):
    """交易计划条目（buy 必填买点区间；sell 必填止盈；两类均必填止损）。"""

    stock_code: str
    plan_type: Literal["buy", "sell"]
    strategy: str
    buy_zone_low: float | None
    buy_zone_high: float | None
    target_price: float | None
    stop_loss: float
    position_pct: float
    basis: str

    @field_validator("plan_type", mode="before")
    @classmethod
    def _normalize_plan_type(cls, value: Any) -> Any:
        """边界归一：中文计划类型（买入/卖出）映射回白名单字面量。"""
        if isinstance(value, str):
            mapping = {"买入": "buy", "开仓": "buy", "卖出": "sell", "清仓": "sell"}
            return mapping.get(value.strip(), value)
        return value


class AgentDailyPlanContent(BaseModel):
    """每日计划结构化输出契约（ai_analysis_result.structured_output 形状）。"""

    trade_date: str
    selections: list[PlanSelectionItem]
    plans: list[PlanTradePlanItem]


@dataclass(slots=True)
class PlanGenerateResult:
    """生成结果：内容 + 是否缓存命中 + 剔除明细（任务 metadata 用）。"""

    content: AgentDailyPlanContent
    cached: bool
    dropped_codes: list[str]
