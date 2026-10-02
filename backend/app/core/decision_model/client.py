"""判断模型调用面（内部契约，D23 ``DecisionModelClient.ask``）。

L1 调用方只依赖本类：一条 llm_config（purpose=decision）解析后构造一个实例，
携带该配置的 adapter 与阈值组——影子期主臂/对照臂各持一个实例，答案的
model/usage/latency 与阈值组同源，observation 落库与网控判定所需字段齐全。
"""

from collections.abc import Mapping
from typing import Any

from app.core.decision_model.adapter import DecisionModelAdapter
from app.core.decision_model.contracts import (
    DecisionThresholds,
    JudgeQuestion,
    JudgeResponse,
)


class DecisionModelClient:
    """单配置判断模型客户端（vendor 无关调用面）。"""

    def __init__(
        self,
        adapter: DecisionModelAdapter,
        *,
        config_id: int,
        model_name: str,
        thresholds: DecisionThresholds,
    ) -> None:
        self._adapter = adapter
        self.config_id = config_id
        self.model_name = model_name
        self.thresholds = thresholds

    async def ask(
        self, state: Mapping[str, Any], questions: Mapping[str, JudgeQuestion]
    ) -> JudgeResponse:
        """投递判断请求（透传 adapter；异常层次见 errors 模块文档）。"""
        return await self._adapter.ask(state, questions)
