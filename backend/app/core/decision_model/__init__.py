"""判断模型接入层（D23）：System One 品类接口契约的 vendor 无关封装。

core 叶子模块——任何层可顶层导入；DB 解析与 failover 编排在服务层
（``app.services.admin.decision_model_service``）。设计见 paper-trading-plan §11.6。
"""

from app.core.decision_model.adapter import DecisionModelAdapter, SystemOneAdapter
from app.core.decision_model.client import DecisionModelClient
from app.core.decision_model.contracts import (
    DEFAULT_THRESHOLDS,
    DecisionThresholds,
    JudgeAnswer,
    JudgeChoice,
    JudgeChoiceAnswer,
    JudgeNoul,
    JudgeNoulAnswer,
    JudgeNoulCriteria,
    JudgeQuestion,
    JudgeResponse,
    JudgeScore,
    JudgeScoreAnswer,
    JudgeUsage,
    thresholds_from_extra,
)
from app.core.decision_model.errors import (
    DecisionModelConfigError,
    DecisionModelError,
    DecisionModelRequestError,
    DecisionModelResponseError,
    DecisionModelUnavailableError,
)

__all__ = [
    "DEFAULT_THRESHOLDS",
    "DecisionModelAdapter",
    "DecisionModelClient",
    "DecisionModelConfigError",
    "DecisionModelError",
    "DecisionModelRequestError",
    "DecisionModelResponseError",
    "DecisionModelUnavailableError",
    "DecisionThresholds",
    "JudgeAnswer",
    "JudgeChoice",
    "JudgeChoiceAnswer",
    "JudgeNoul",
    "JudgeNoulAnswer",
    "JudgeNoulCriteria",
    "JudgeQuestion",
    "JudgeResponse",
    "JudgeScore",
    "JudgeScoreAnswer",
    "JudgeUsage",
    "SystemOneAdapter",
    "thresholds_from_extra",
]
