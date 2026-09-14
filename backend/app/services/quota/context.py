"""计量上下文：ContextVar 携带本次 AI 调用的属主与功能分类。

api / celery / agent 三方共导入的叶子模块（无其他依赖）。入口用
``meter_scope`` 包住执行体，``UsageMeterCallback`` 在模型回调时读取，
ContextVar 随 asyncio 任务创建自动向下游传播。
"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from app.services.quota.constants import UsageFeature


@dataclass(frozen=True)
class MeterContext:
    """一次 AI 请求的计量上下文。

    user_id 为 None 表示系统维度（Celery 定时任务）：计量入 system 分类、
    不占任何个人配额。
    """

    user_id: int | None
    feature: UsageFeature


meter_context: ContextVar[MeterContext | None] = ContextVar(
    "meter_context", default=None
)


def current_meter_context() -> MeterContext | None:
    """读取当前计量上下文（未设置返回 None，调用方按不计费处理）。"""
    return meter_context.get()


@contextmanager
def meter_scope(user_id: int | None, feature: UsageFeature) -> Iterator[MeterContext]:
    """在当前执行上下文内绑定计量上下文（同步 CM，async 代码同样适用）。"""
    ctx = MeterContext(user_id=user_id, feature=feature)
    token = meter_context.set(ctx)
    try:
        yield ctx
    finally:
        meter_context.reset(token)
