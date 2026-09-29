"""判断模型内部契约（D23）：三题型 + 答案 + 响应 + 阈值组。

System One 品类接口契约（state + 类型化问题 → 类型化概率答案 + confidence）的
vendor 无关内部投影——押注接口形状，不押注厂商（paper-trading-plan §11.6）。
字段全部 required（禁默认值，项目铁律）。

题型语义（§11.3）：
- Choice：N 选一（2-255 项），答案含 probabilities + confidence
- Score：2-10 级有序量表，答案含 score（可落级间，如 1.035）+ confidence
- Noul：是/否概率——**无 confidence 字段，数字本身即信念**

阈值组按 model_version 键控的落地：一条 llm_config（purpose=decision）钉住一个
版本 pin，``extra.thresholds`` 即该版本的阈值组——行级配置天然 per-vendor/
per-version 键控（D24），影子期校准后 admin 改 extra 即时生效。
"""

from collections.abc import Mapping
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.decision_model.errors import DecisionModelConfigError


class JudgeNoulCriteria(BaseModel):
    """Noul 是/否两极的判据（wire 字段名 ``true``/``false``）。"""

    model_config = ConfigDict(populate_by_name=True)

    criterion_true: str = Field(alias="true")
    criterion_false: str = Field(alias="false")


class JudgeNoul(BaseModel):
    """是/否判断题：返回 p(yes)，无 confidence（数字本身即信念，§11.3）。"""

    instructions: str = Field(..., min_length=1)
    criteria: JudgeNoulCriteria

    def to_wire(self) -> dict[str, Any]:
        """序列化为 systemone wire 形状（含题型判别字段）。"""
        return {
            "type": "noul",
            "instructions": self.instructions,
            "criteria": self.criteria.model_dump(by_alias=True),
        }


class JudgeChoice(BaseModel):
    """N 选一题（2-255 项全集）：应传全集并设显式 ``other`` 项（§11.3）。"""

    instructions: str = Field(..., min_length=1)
    criteria: dict[str, str]

    @field_validator("criteria")
    @classmethod
    def _check_option_count(cls, value: dict[str, str]) -> dict[str, str]:
        if not 2 <= len(value) <= 255:
            raise ValueError("Choice 选项数须在 2-255 之间")
        return value

    def to_wire(self) -> dict[str, Any]:
        """序列化为 systemone wire 形状（含题型判别字段）。"""
        return {
            "type": "choice",
            "instructions": self.instructions,
            "criteria": self.criteria,
        }


class JudgeScore(BaseModel):
    """有序量表题（2-10 级）：score 可落在级间，legend 随答案返回。"""

    instructions: str = Field(..., min_length=1)
    criteria: list[str]

    @field_validator("criteria")
    @classmethod
    def _check_level_count(cls, value: list[str]) -> list[str]:
        if not 2 <= len(value) <= 10:
            raise ValueError("Score 级数须在 2-10 之间")
        return value

    def to_wire(self) -> dict[str, Any]:
        """序列化为 systemone wire 形状（含题型判别字段）。"""
        return {
            "type": "score",
            "instructions": self.instructions,
            "criteria": self.criteria,
        }


JudgeQuestion = JudgeNoul | JudgeChoice | JudgeScore


class JudgeChoiceAnswer(BaseModel):
    """Choice 答案：选中项 + 全项概率 + 置信度（分布集中度，§11.3）。"""

    type: Literal["choice"]
    choice: str
    probabilities: dict[str, float]
    confidence: float


class JudgeScoreAnswer(BaseModel):
    """Score 答案：概率加权位置（级间可落）+ 全级概率 + 置信度 + 级别图例。"""

    type: Literal["score"]
    score: float
    probabilities: dict[str, float]
    confidence: float
    legend: dict[str, str]


class JudgeNoulAnswer(BaseModel):
    """Noul 答案：p(yes)，无 confidence——数字本身即信念（§11.3）。"""

    type: Literal["noul"]
    noul: float


JudgeAnswer = Annotated[
    JudgeChoiceAnswer | JudgeScoreAnswer | JudgeNoulAnswer,
    Field(discriminator="type"),
]


class JudgeUsage(BaseModel):
    """用量（observation 落库与成本对账依赖）。

    ``cost`` 为 USD 计费额（OpenRouter 返回；直连 vendor 语义未证 → 可选）。
    """

    input_tokens: int
    output_tokens: int
    cost: float | None


class JudgeResponse(BaseModel):
    """判断模型响应（内部契约）：版本/用量/延迟一律随响应返回（D23）。"""

    model_config = ConfigDict(frozen=True)

    #: 实际服务的模型版本（响应 ``model`` 字段，如 ``typesafe/jev-1.13-20260917``；
    #: pin 纪律——``jev-latest`` 会漂移，观测以本字段为准）
    model: str
    answers: dict[str, JudgeAnswer]
    usage: JudgeUsage
    request_id: str | None
    latency_ms: int
    #: 服务配置的 llm_config.id（observation 归因；测试直构 adapter 时可为 None）
    config_id: int | None


class DecisionThresholds(BaseModel):
    """按动作代价分档的置信阈值组（§11.1/§11.3）。

    L1 网控语义：answer.confidence（Noul 用 noul 值本身）低于对应档位阈值
    → 不动作 + 留痕（低置信不等于不作为，等于移交）。
    """

    model_config = ConfigDict(frozen=True)

    #: 观察类动作（只读判断/留痕类）的置信下限
    observe: float
    #: 资金动作（真实买入开仓）的置信下限
    fund_action: float
    #: 离场动作（止盈/止损卖出）的置信下限——离场是防御动作，错做代价
    #: （少赚反弹）远小于不做代价（继续承损），不要求与开仓同等置信
    exit_action: float = 0.60

    @field_validator("observe", "fund_action", "exit_action")
    @classmethod
    def _check_range(cls, value: float) -> float:
        if not 0 < value < 1:
            raise ValueError("置信阈值须在 (0, 1) 开区间内")
        return value

    @model_validator(mode="after")
    def _check_ordering(self) -> "DecisionThresholds":
        if self.fund_action <= self.observe:
            raise ValueError("资金动作阈值须高于观察类阈值")
        if not self.observe <= self.exit_action <= self.fund_action:
            raise ValueError("离场档须在 [观察档, 资金档] 区间内")
        return self


#: §11.1 起步分档（观察 0.6 / 离场 0.6 / 资金动作 0.85），影子期校准后按配置覆盖
DEFAULT_THRESHOLDS: DecisionThresholds = DecisionThresholds(
    observe=0.6, fund_action=0.85, exit_action=0.60
)


def thresholds_from_extra(extra: Mapping[str, Any]) -> DecisionThresholds:
    """从 ``llm_config.extra['thresholds']`` 解析阈值组；缺省回起步档。

    配置了非法值（越界/类型错/资金档不高于观察档）抛 ``DecisionModelConfigError``
    ——admin 改错即时暴露，而非静默回退默认掩盖配置漂移。

    Args:
        extra: llm_config.extra 字典（形如 ``{"thresholds": {"observe": ..}}``）

    Returns:
        解析后的阈值组

    Raises:
        DecisionModelConfigError: thresholds 存在但形状或取值非法
    """
    raw = extra.get("thresholds")
    if raw is None:
        return DEFAULT_THRESHOLDS
    if not isinstance(raw, Mapping):
        raise DecisionModelConfigError(
            "extra.thresholds 须为对象（observe/fund_action/exit_action）"
        )
    try:
        payload: dict[str, Any] = {"observe": raw["observe"], "fund_action": raw["fund_action"]}
        if "exit_action" in raw:
            payload["exit_action"] = raw["exit_action"]
        return DecisionThresholds(**payload)
    except (KeyError, TypeError, ValueError) as exc:
        raise DecisionModelConfigError(f"extra.thresholds 非法: {exc}") from exc
