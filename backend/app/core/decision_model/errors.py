"""判断模型异常层次（advisory 语义，D23）。

判断模型不可用**不是故障**——L1 跳过、tick 循环照常、observation 记录降级原因；
任何子类都不应中断调用方循环，由调用方（批次 8a L1）捕获后降级纯 L0。

- ``DecisionModelUnavailableError``：暂不可用（超时/连接失败/限流/过载/额度类）
  ——failover 候选，冷却期后自愈
- ``DecisionModelRequestError``：请求本身有错（认证失败/pin 不存在/题面校验不过）
  ——配置或代码 bug，重试与切换备用无意义
- ``DecisionModelResponseError``：HTTP 200 但响应形状不符契约（vendor 端漂移）
  ——failover 候选（备用臂可能仍正常）
"""

from typing import ClassVar


class DecisionModelError(Exception):
    """判断模型异常基类。"""

    default_message: ClassVar[str] = "判断模型调用失败"

    def __init__(
        self, message: str | None = None, *, status_code: int | None = None
    ) -> None:
        super().__init__(message or self.default_message)
        self.status_code = status_code


class DecisionModelUnavailableError(DecisionModelError):
    """判断模型暂不可用——failover 候选；调用方降级纯 L0（非故障）。"""

    default_message = "判断模型暂不可用"


class DecisionModelRequestError(DecisionModelError):
    """请求被上游拒绝（401/403/400/404/422）——配置或题面 bug，不当次重试。"""

    default_message = "判断模型请求被拒绝"


class DecisionModelConfigError(DecisionModelRequestError):
    """本地配置非法（如 extra.thresholds 越界）——解析期即暴露，不发起请求。"""

    default_message = "判断模型配置非法"


class DecisionModelResponseError(DecisionModelError):
    """HTTP 200 但响应形状不符契约（vendor 端漂移）——failover 候选。"""

    default_message = "判断模型响应不符合契约"
