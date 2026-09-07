"""TaskSpec：采集任务的声明式配置单元。"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class TaskSpec:
    """一个采集任务的声明式配置。"""

    name: str
    label: str
    data_type: str
    collectors: dict[str, str]
    queue: Literal["realtime", "batch", "heavy"] | None = None
    soft_time_limit: int | None = None
    hard_time_limit: int | None = None
    max_retries: int | None = None
    config_params: tuple[str, ...] = ()
    run_params: tuple[str, ...] = ()
    defaults: dict[str, Any] = field(default_factory=dict)
    converters: dict[str, Callable[[Any], Any]] = field(default_factory=dict)

    @property
    def param_keys(self) -> tuple[str, ...]:
        """任务级参数全集（runner 据此从请求参数中挑选 kwargs）。"""
        return self.config_params + self.run_params
