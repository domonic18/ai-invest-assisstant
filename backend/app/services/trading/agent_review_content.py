"""模拟盘复盘内容契约（LLM 结构化输出 + 持久化读模型）。

复盘分层判定的 Pydantic 契约单点：字段禁默认值（进 JSON Schema required，
LLM 必须对每层显式表态）；旧缓存行缺新增键由 before-validator 补空值兼容
读取（校验器不影响 LLM schema）。编排/取数/LLM 调用见
``agent_review_service`` / ``agent_review_inputs``。
"""

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

#: 复盘窗口粒度（API 入参与 LLM 契约共用）
ReviewPeriod = Literal["day", "week", "month"]

#: 预检无复盘对象时落缓存行的系统标记原因（展示层据此与「未执行」区分）
NO_TARGET_REASON = "复盘窗口内无委托成交，账户亦无历史持仓（空仓无复盘对象）"


class TradeVerdict(BaseModel):
    """单笔委托的三层判定（字段禁默认值——LLM 必须对每层显式表态）。"""

    cl_ord_id: str
    stock_code: str
    selection_verdict: Literal["correct", "wrong", "neutral"]
    plan_verdict: Literal["correct", "wrong", "neutral"]
    execution_verdict: Literal["correct", "wrong", "neutral"]
    reason: str


class ReviewExperience(BaseModel):
    """复盘提取的经验条目（批次 9 幂等入库 agent_memory 的直接来源）。"""

    title: str
    body: str
    mem_type: Literal["discipline", "method", "lesson"]


class MethodologyCheckItem(BaseModel):
    """单条 KB 纪律的方法论验证结论（逐条表态，禁默认值——LLM 必须对每条显式判定）。"""

    title: str
    verdict: Literal["followed", "violated", "not_applicable"]
    note: str


class PaperTradeReviewContent(BaseModel):
    """复盘 LLM 结构化输出契约（字段禁默认值，进 JSON Schema required）。

    D34 新增 market_context（盘面语境归纳）与 methodology_check（KB 纪律
    逐条验证）；旧缓存行缺这两键由 before-validator 补空值兼容读取。
    no_target_reason：预检无复盘对象（空仓）时由系统填入的标记（LLM 恒为
    null）；全空内容且无标记视为 LLM 偷懒输出，校验失败触发重试。
    """

    period: ReviewPeriod
    trade_date: str
    overall: str
    trades: list[TradeVerdict]
    bias: str
    suggestion: str
    market_context: str
    methodology_check: list[MethodologyCheckItem]
    experiences: list[ReviewExperience]
    no_target_reason: str | None = Field(
        description="无复盘对象标记：预检发现窗口内无交易且无持仓时由系统填入；"
        "正常复盘必须为 null，内容字段不可全空"
    )

    @model_validator(mode="before")
    @classmethod
    def _backfill_d34_keys(cls, value: Any) -> Any:
        """D34 前生成的缓存行缺 market_context/methodology_check、本字段新增前
        缓存行缺 no_target_reason：补空值兼容（skill_id/input_hash 未变，旧复盘
        必须可读；校验器不影响 LLM schema）。"""
        if isinstance(value, dict):
            value = {**value}
            value.setdefault("market_context", "")
            value.setdefault("methodology_check", [])
            value.setdefault("no_target_reason", None)
        return value

    @model_validator(mode="after")
    def _require_content_when_target_exists(self) -> "PaperTradeReviewContent":
        """复盘只在有对象时进入 LLM：全空内容且无无对象标记 = 偷懒输出，
        抛错交由结构化输出重试机制。"""
        if (
            self.no_target_reason is None
            and not self.trades
            and not self.overall.strip()
            and not self.bias.strip()
            and not self.suggestion.strip()
        ):
            raise ValueError(
                "复盘内容全空（overall/bias/suggestion/trades 均空）且无 "
                "no_target_reason：窗口内存在复盘对象时必须输出实质复盘内容"
            )
        return self

    @field_validator("suggestion", mode="before")
    @classmethod
    def _join_suggestion_list(cls, value: Any) -> Any:
        """「不超过 3 条」会诱导 LLM 输出数组：容忍 list 归一为多行文本。"""
        if isinstance(value, list):
            return "\n".join(str(item) for item in value)
        return value

    @field_validator("experiences", mode="before")
    @classmethod
    def _normalize_experience_keys(cls, value: Any) -> Any:
        """MiniMax 对 output_format 的字段名遵循度差（trigger/action 代
        title/body）：边界处按别名归一，避免整次生成作废重烧。"""
        if isinstance(value, list):
            normalized: list[Any] = []
            for item in value:
                if isinstance(item, dict) and "title" not in item and "trigger" in item:
                    item = {
                        **item,
                        "title": item["trigger"],
                        "body": item.get("action") or item.get("body", ""),
                    }
                    item.pop("trigger", None)
                    item.pop("action", None)
                normalized.append(item)
            return normalized
        return value


class PaperTradeReviewRecord(PaperTradeReviewContent):
    """复盘持久化读模型（structured_output 实际形状）：LLM 契约 + 落库时
    注入的 agent_key（读取按 Agent 过滤；不进 LLM schema）。"""

    agent_key: str


@dataclass(slots=True)
class ReviewGenerateResult:
    """生成结果：内容 + 是否缓存命中（任务 metadata 用）。"""

    content: PaperTradeReviewContent
    cached: bool
