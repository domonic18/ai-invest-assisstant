"""模拟盘复盘生成采集器（internal 渠道，heavy 队列）。

19:00 串行在盘后同步与大盘 AI 复盘（18:35）之后（D30 重排，实例名
paper_trade_review_1610 沿用）。执行主体按通道拆分：

- ``paper_trade_review_scheduled``：循环 active Agent 按 review_cadence 生成
  日/周/月复盘（单 Agent 异常隔离，未就绪交由 Celery 退避重试）
- ``paper_trade_review_on_demand``：params 带 ``agent_key`` 时只生成该 Agent
  的指定窗口（页面接口 / Agent 工具派生同一任务，季/半年/年只走此路径）

本模块只保留采集器外壳（collect/transform/validate + run 分流）。
"""

from typing import Any

from collector.core.base import BaseCollector, CollectResult
from collector.spiders.paper_trade_review_on_demand import run_on_demand
from collector.spiders.paper_trade_review_scheduled import run_scheduled


class PaperTradeReviewCollector(BaseCollector):
    """模拟盘复盘生成器（定时日/周/月 + 按需单周期，不直接写表）。"""

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        """占位实现：实际生成逻辑在 ``run`` 中委托给 service。"""
        return []

    async def transform(self, raw: dict[str, Any]) -> dict[str, Any]:
        return raw

    async def validate(self, item: dict[str, Any]) -> bool:
        return True

    async def run(self, **kwargs: Any) -> CollectResult:
        """按需单 Agent 生成，或循环 active Agent 生成/复用当日复盘。"""
        agent_key = kwargs.pop("agent_key", None)
        if agent_key:
            return await run_on_demand(
                self.source, self.data_type, str(agent_key), **kwargs
            )
        return await run_scheduled(self.source, self.data_type, **kwargs)
