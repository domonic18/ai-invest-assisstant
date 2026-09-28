"""System One wire 协议 adapter（vendor 无关，D23）。

任意实现 systemone 形状（``POST {base}/v1/systemone``，body ``{model, state,
questions}``）的端点配 base_url + api_key + model pin 直用——TypeSafe 直连 /
OpenRouter / Codiv(openjev) / 未来自托管复刻端点皆为同一 adapter 的不同配置
（2026-09-28 鉴权探针实证：成功路径 wire 忠实，差异仅在错误信封与个别响应头）。

错误信封双形状兼容（探针③）：
- OpenRouter：``{"error": {"message", "code"}}``（422 校验列表串化进 message）
- Jev/Codiv 直连：``{"detail": {"error_type", "message"}}``；422 为校验列表

裸 httpx 直调而非 typesafe-sdk（探针④：SDK 响应模型缺 id/usage.cost 映射，
自解析原始体更可控；对齐 PaperTradeClient 等自定义协议客户端先例）。
"""

import time
from collections.abc import Mapping
from typing import Any, Protocol

import httpx
import structlog
from pydantic import TypeAdapter, ValidationError

from app.core.decision_model.contracts import (
    JudgeAnswer,
    JudgeQuestion,
    JudgeResponse,
    JudgeUsage,
)
from app.core.decision_model.errors import (
    DecisionModelRequestError,
    DecisionModelResponseError,
    DecisionModelUnavailableError,
)
from app.utils.api_base import normalize_api_base

logger = structlog.get_logger(__name__)

_SYSTEMONE_PATH: str = "/v1/systemone"

_answers_adapter: TypeAdapter[dict[str, JudgeAnswer]] = TypeAdapter(
    dict[str, JudgeAnswer]
)

#: 状态码 → 异常类：4xx 请求类（重试无意义），402/429/5xx 暂不可用类（failover 候选）
_REQUEST_STATUS = frozenset({400, 401, 403, 404, 405, 422})


class DecisionModelAdapter(Protocol):
    """判断模型 adapter 协议：未来厂商 = 新 adapter，内部契约与调用面零改动。"""

    async def ask(
        self, state: Mapping[str, Any], questions: Mapping[str, JudgeQuestion]
    ) -> JudgeResponse:
        """一次请求并行投递全部题型（speculative fan-out，§11.3）。"""
        ...


def _error_message(response: httpx.Response) -> str:
    """从双形状错误信封提取可读信息；解析失败回退原文截断。"""
    try:
        payload: Any = response.json()
    except ValueError:
        return response.text[:200]
    if isinstance(payload, dict):
        err = payload.get("error")
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])[:300]
        detail = payload.get("detail")
        if isinstance(detail, dict) and detail.get("message"):
            return f"{detail.get('error_type', 'error')}: {str(detail['message'])[:300]}"
        if isinstance(detail, list):
            return f"校验失败: {str(detail)[:300]}"
        if isinstance(detail, str) and detail:
            return detail[:300]
    return response.text[:200]


class SystemOneAdapter:
    """systemone wire 协议 adapter（``transport`` 参数供测试注入）。"""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float,
        config_id: int | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._url = normalize_api_base(base_url) + _SYSTEMONE_PATH
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._config_id = config_id
        self._transport = transport

    async def ask(
        self, state: Mapping[str, Any], questions: Mapping[str, JudgeQuestion]
    ) -> JudgeResponse:
        """投递一次判断请求（多题型并行），翻译异常与信封差异。

        Args:
            state: 盘面状态（只放题面需要的字段——context rot 纪律，§11.3）
            questions: 按 question key 键控的题型（长数组位置索引不可靠，
                批量问必须键控对象而非数组序）

        Returns:
            内部契约响应（版本/用量/延迟随响应返回）

        Raises:
            DecisionModelUnavailableError: 超时/网络不可达/限流/过载/额度类
            DecisionModelRequestError: 认证失败/pin 不存在/题面校验不过
            DecisionModelResponseError: 200 但形状不符契约
        """
        payload = {
            "model": self._model,
            "state": dict(state),
            "questions": {key: q.to_wire() for key, q in questions.items()},
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        started = time.monotonic()
        try:
            # 短连接：分钟级 tick 节奏，免长连接生命周期管理（项目惯例）
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds, transport=self._transport
            ) as client:
                response = await client.post(self._url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise DecisionModelUnavailableError(f"判断模型超时: {exc}") from exc
        except httpx.HTTPError as exc:
            raise DecisionModelUnavailableError(f"判断模型网络不可达: {exc}") from exc
        latency_ms = int((time.monotonic() - started) * 1000)
        if response.status_code != 200:
            self._raise_for_status(response)
        return self._parse(response, latency_ms)

    def _raise_for_status(self, response: httpx.Response) -> None:
        """按状态码与信封归类非 200 响应。"""
        message = _error_message(response)
        status = response.status_code
        if status in _REQUEST_STATUS:
            raise DecisionModelRequestError(
                f"判断模型请求被拒绝（HTTP {status}）: {message}", status_code=status
            )
        # 402 额度 / 429 限流 / 529 过载 / 其余 5xx 上游故障 → 暂不可用语义
        raise DecisionModelUnavailableError(
            f"判断模型暂不可用（HTTP {status}）: {message}", status_code=status
        )

    def _parse(self, response: httpx.Response, latency_ms: int) -> JudgeResponse:
        """解析 200 响应为内部契约；形状不符抛 DecisionModelResponseError。"""
        try:
            body: Any = response.json()
        except ValueError as exc:
            raise DecisionModelResponseError(
                f"判断模型返回非 JSON: {response.text[:200]}"
            ) from exc
        if not isinstance(body, dict):
            raise DecisionModelResponseError("判断模型响应体不是对象")
        model_version = body.get("model")
        answers_raw = body.get("answers")
        usage_raw = body.get("usage")
        if not isinstance(model_version, str) or not model_version:
            raise DecisionModelResponseError("响应缺少 model 字段（版本留痕依赖）")
        if not isinstance(answers_raw, dict):
            raise DecisionModelResponseError("响应缺少 answers 对象")
        try:
            answers = _answers_adapter.validate_python(answers_raw)
        except ValidationError as exc:
            raise DecisionModelResponseError(
                f"answers 形状不符契约: {str(exc)[:300]}"
            ) from exc
        if not isinstance(usage_raw, dict):
            raise DecisionModelResponseError("响应缺少 usage 对象")
        try:
            usage = JudgeUsage(
                input_tokens=usage_raw["input_tokens"],
                output_tokens=usage_raw["output_tokens"],
                cost=usage_raw.get("cost"),
            )
        except (KeyError, TypeError) as exc:
            raise DecisionModelResponseError(
                f"usage 形状不符契约: {exc}"
            ) from exc
        request_id = body.get("id")
        logger.debug(
            "decision_model_ask",
            model=model_version,
            latency_ms=latency_ms,
            input_tokens=usage.input_tokens,
            questions=len(answers),
        )
        return JudgeResponse(
            model=model_version,
            answers=answers,
            usage=usage,
            request_id=request_id if isinstance(request_id, str) else None,
            latency_ms=latency_ms,
            config_id=self._config_id,
        )
