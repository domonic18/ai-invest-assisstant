"""UsageMeterCallback 计量状态机单测：预扣/结算/估算/error 回补/去重。"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from app.agent.runtime.usage_meter import UsageMeterCallback, _extract_usage
from app.services.quota.constants import FEATURE_ASSISTANT, FEATURE_PAGE, OUTLET_BYOK, OUTLET_SYSTEM
from app.services.quota.context import meter_scope
from app.services.quota.quota_service import RESERVE_DEGRADED, RESERVE_DENIED
from app.services.quota.usage_writer import UsageRecord

pytestmark = pytest.mark.unit


def _result_with_usage(prompt_tokens: int, completion_tokens: int) -> LLMResult:
    message = AIMessage(
        content="答案",
        usage_metadata={
            "input_tokens": prompt_tokens,
            "output_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    )
    return LLMResult(generations=[[ChatGeneration(message=message)]])


def _result_without_usage() -> LLMResult:
    return LLMResult(generations=[[ChatGeneration(message=AIMessage(content="答案"))]])


@pytest.mark.asyncio
async def test_real_usage_settles_and_records() -> None:
    callback = UsageMeterCallback(outlet=OUTLET_SYSTEM, provider="openai", model_name="m1")
    run_id = uuid.uuid4()
    enqueued: list[UsageRecord] = []
    with (
        patch(
            "app.agent.runtime.usage_meter.quota_service.check_and_reserve",
            AsyncMock(return_value=99999),
        ) as reserve,
        patch(
            "app.agent.runtime.usage_meter.quota_service.settle", AsyncMock()
        ) as settle,
        patch("app.agent.runtime.usage_meter.enqueue", side_effect=enqueued.append),
    ):
        with meter_scope(7, FEATURE_ASSISTANT):
            await callback.on_chat_model_start({}, [[HumanMessage(content="你好世界")]], run_id=run_id)
            await callback.on_llm_end(_result_with_usage(10, 5), run_id=run_id)

    reserve.assert_awaited_once()
    settle.assert_awaited_once_with(7, reserve.call_args.args[1], 15)
    assert len(enqueued) == 1
    record = enqueued[0]
    assert (record.user_id, record.feature, record.outlet) == (7, "assistant", "system")
    assert (record.prompt_tokens, record.completion_tokens, record.total_tokens) == (10, 5, 15)
    assert record.estimated is False
    assert callback._inflight == {}


@pytest.mark.asyncio
async def test_missing_usage_falls_back_to_estimate() -> None:
    callback = UsageMeterCallback(outlet=OUTLET_SYSTEM, provider="openai", model_name="m1")
    run_id = uuid.uuid4()
    enqueued: list[UsageRecord] = []
    with (
        patch(
            "app.agent.runtime.usage_meter.quota_service.check_and_reserve",
            AsyncMock(return_value=99999),
        ),
        patch("app.agent.runtime.usage_meter.quota_service.settle", AsyncMock()),
        patch("app.agent.runtime.usage_meter.enqueue", side_effect=enqueued.append),
    ):
        with meter_scope(7, FEATURE_PAGE):
            await callback.on_chat_model_start({}, [[HumanMessage(content="复盘总结")]], run_id=run_id)
            await callback.on_llm_end(_result_without_usage(), run_id=run_id)

    record = enqueued[0]
    assert record.estimated is True
    assert record.prompt_tokens == 4  # CJK 逐字估算


@pytest.mark.asyncio
async def test_quota_denied_still_reserves_and_records() -> None:
    """LangChain 会吞 callback 异常，拒绝路径不抛——照常预扣与计量，
    把镜像扣至负值；请求级拦截由入口 precheck 承担。"""
    callback = UsageMeterCallback(outlet=OUTLET_SYSTEM, provider="openai", model_name="m1")
    run_id = uuid.uuid4()
    enqueued: list[UsageRecord] = []
    with (
        patch(
            "app.agent.runtime.usage_meter.quota_service.check_and_reserve",
            AsyncMock(return_value=RESERVE_DENIED),
        ) as reserve,
        patch("app.agent.runtime.usage_meter.quota_service.settle", AsyncMock()),
        patch("app.agent.runtime.usage_meter.enqueue", side_effect=enqueued.append),
    ):
        with meter_scope(7, FEATURE_ASSISTANT):
            await callback.on_chat_model_start(
                {}, [[HumanMessage(content="你好")]], run_id=run_id
            )
            # 不抛异常，调用照常完成并计量
            await callback.on_llm_end(_result_with_usage(2, 1), run_id=run_id)

    reserve.assert_awaited_once()
    assert len(enqueued) == 1
    assert enqueued[0].user_id == 7
    assert callback._inflight == {}


@pytest.mark.asyncio
async def test_byok_outlet_skips_quota_but_records() -> None:
    callback = UsageMeterCallback(outlet=OUTLET_BYOK, provider="byok", model_name="user-m")
    run_id = uuid.uuid4()
    enqueued: list[UsageRecord] = []
    with (
        patch(
            "app.agent.runtime.usage_meter.quota_service.check_and_reserve",
            AsyncMock(),
        ) as reserve,
        patch("app.agent.runtime.usage_meter.enqueue", side_effect=enqueued.append),
    ):
        with meter_scope(7, FEATURE_ASSISTANT):
            await callback.on_chat_model_start({}, [[HumanMessage(content="你好")]], run_id=run_id)
            await callback.on_llm_end(_result_with_usage(3, 2), run_id=run_id)

    reserve.assert_not_awaited()
    assert enqueued[0].outlet == "byok"


@pytest.mark.asyncio
async def test_error_refunds_reserved_without_record() -> None:
    callback = UsageMeterCallback(outlet=OUTLET_SYSTEM, provider="openai", model_name="m1")
    run_id = uuid.uuid4()
    enqueued: list[UsageRecord] = []
    with (
        patch(
            "app.agent.runtime.usage_meter.quota_service.check_and_reserve",
            AsyncMock(return_value=99999),
        ) as reserve,
        patch("app.agent.runtime.usage_meter.quota_service.settle", AsyncMock()) as settle,
        patch("app.agent.runtime.usage_meter.enqueue", side_effect=enqueued.append),
    ):
        with meter_scope(7, FEATURE_PAGE):
            await callback.on_chat_model_start({}, [[HumanMessage(content="你好")]], run_id=run_id)
            await callback.on_llm_error(RuntimeError("provider down"), run_id=run_id)

    # 失败调用全额回补、不留用量记录
    settle.assert_awaited_once_with(7, reserve.call_args.args[1], 0)
    assert enqueued == []


@pytest.mark.asyncio
async def test_degraded_passthrough_skips_settle_but_records() -> None:
    """Redis 降级放行未真实预扣：不结算（防镜像恢复后被回补虚增），仍记明细。"""
    callback = UsageMeterCallback(outlet=OUTLET_SYSTEM, provider="openai", model_name="m1")
    run_id = uuid.uuid4()
    enqueued: list[UsageRecord] = []
    with (
        patch(
            "app.agent.runtime.usage_meter.quota_service.check_and_reserve",
            AsyncMock(return_value=RESERVE_DEGRADED),
        ),
        patch(
            "app.agent.runtime.usage_meter.quota_service.settle", AsyncMock()
        ) as settle,
        patch("app.agent.runtime.usage_meter.enqueue", side_effect=enqueued.append),
    ):
        with meter_scope(7, FEATURE_ASSISTANT):
            await callback.on_chat_model_start({}, [[HumanMessage(content="你好")]], run_id=run_id)
            await callback.on_llm_end(_result_with_usage(3, 2), run_id=run_id)

    settle.assert_not_awaited()
    assert len(enqueued) == 1
    assert (enqueued[0].user_id, enqueued[0].total_tokens) == (7, 5)


@pytest.mark.asyncio
async def test_prune_stale_refunds_reserved_entries() -> None:
    """in-flight 超限清理陈旧项：全额回补预扣后丢弃，未过期项保留。"""
    from app.agent.runtime.usage_meter import _MAX_INFLIGHT, _STALE_SECONDS, _RunMeter
    from app.services.quota.context import MeterContext

    callback = UsageMeterCallback(outlet=OUTLET_SYSTEM, provider="openai", model_name="m1")
    stale = _RunMeter(
        ctx=MeterContext(user_id=7, feature=FEATURE_PAGE),
        prompt_text="你好",
        reserved=30,
    )
    stale.started_at -= _STALE_SECONDS + 1
    fresh = _RunMeter(
        ctx=MeterContext(user_id=7, feature=FEATURE_PAGE),
        prompt_text="你好",
        reserved=10,
    )
    callback._inflight = {uuid.uuid4(): stale}
    callback._inflight.update({uuid.uuid4(): fresh for _ in range(_MAX_INFLIGHT)})

    with patch(
        "app.agent.runtime.usage_meter.quota_service.settle", AsyncMock()
    ) as settle:
        await callback._prune_stale()

    settle.assert_awaited_once_with(7, 30, 0)
    assert all(state is not stale for state in callback._inflight.values())
    assert len(callback._inflight) == _MAX_INFLIGHT


@pytest.mark.asyncio
async def test_start_events_dedup_by_run_id() -> None:
    callback = UsageMeterCallback(outlet=OUTLET_SYSTEM, provider="openai", model_name="m1")
    run_id = uuid.uuid4()
    enqueued: list[UsageRecord] = []
    with (
        patch(
            "app.agent.runtime.usage_meter.quota_service.check_and_reserve",
            AsyncMock(return_value=99999),
        ) as reserve,
        patch("app.agent.runtime.usage_meter.enqueue", side_effect=enqueued.append),
    ):
        with meter_scope(7, FEATURE_PAGE):
            # chat 模型开始事件 + LLM 开始事件同 run_id：只预扣一次
            await callback.on_chat_model_start({}, [[HumanMessage(content="你好")]], run_id=run_id)
            await callback.on_llm_start({}, ["你好"], run_id=run_id)
            await callback.on_llm_end(_result_with_usage(2, 1), run_id=run_id)

    assert reserve.await_count == 1
    assert len(enqueued) == 1
    assert enqueued[0].user_id == 7


@pytest.mark.asyncio
async def test_unwrapped_call_counts_as_system_dimension() -> None:
    """未包裹 meter_scope 的调用（Celery 直调等）按系统维度记账，不查配额。"""
    callback = UsageMeterCallback(outlet=OUTLET_SYSTEM, provider="openai", model_name="m1")
    run_id = uuid.uuid4()
    enqueued: list[UsageRecord] = []
    with (
        patch(
            "app.agent.runtime.usage_meter.quota_service.check_and_reserve",
            AsyncMock(),
        ) as reserve,
        patch("app.agent.runtime.usage_meter.enqueue", side_effect=enqueued.append),
    ):
        await callback.on_chat_model_start({}, [[HumanMessage(content="你好")]], run_id=run_id)
        await callback.on_llm_end(_result_with_usage(2, 1), run_id=run_id)

    reserve.assert_not_awaited()
    assert len(enqueued) == 1
    assert enqueued[0].user_id is None
    assert enqueued[0].feature == "system"


def test_extract_usage_from_llm_output() -> None:
    message = AIMessage(content="答案")
    result = LLMResult(
        generations=[[ChatGeneration(message=message)]],
        llm_output={"token_usage": {"prompt_tokens": 7, "completion_tokens": 3}},
    )
    assert _extract_usage(result) == (7, 3)
