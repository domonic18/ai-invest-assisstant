"""skill 链路 LLM 主备切换测试（额度耗尽 → 标记冷却 → 重新解析 → 换模型重跑）。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import openai
import pytest

from app.agent.skills.skill_failover import run_with_llm_failover


def _rate_limit_error() -> openai.RateLimitError:
    return openai.RateLimitError(
        "You've reached your 5-hour usage limit",
        response=SimpleNamespace(status_code=429, headers={}, request=None),
        body=None,
    )


@pytest.mark.unit
class TestRunWithLLMFailover:
    @pytest.mark.asyncio
    async def test_switches_to_backup_and_reruns_on_rate_limit(self) -> None:
        """额度耗尽：主配置进冷却，重新解析切到备用后重跑成功。"""
        primary = SimpleNamespace(config_id=1, model_name="m1")
        backup = SimpleNamespace(config_id=2, model_name="m2")
        calls: list[object] = []

        async def _run(cfg: SimpleNamespace) -> str:
            calls.append(cfg)
            if len(calls) == 1:
                raise _rate_limit_error()
            return "ok"

        resolve = AsyncMock(side_effect=[primary, backup])
        with (
            patch(
                "app.agent.skills.skill_failover.mark_unhealthy", new=AsyncMock()
            ) as p_mark,
            patch(
                "app.agent.skills.skill_failover.classify_llm_error",
                return_value=True,
            ),
        ):
            result, cfg = await run_with_llm_failover(
                resolve, _run, task_key="market_daily_review"
            )

        assert result == "ok"
        assert cfg is backup
        assert [c.config_id for c in calls] == [1, 2]
        p_mark.assert_awaited_once_with(1)

    @pytest.mark.asyncio
    async def test_reraises_when_no_backup_available(self) -> None:
        """无备用可切（健康门仍返回主配置）：原样上抛，不重复消耗死模型。"""
        primary = SimpleNamespace(config_id=1, model_name="m1")
        calls: list[object] = []

        async def _run(cfg: SimpleNamespace) -> str:
            calls.append(cfg)
            raise _rate_limit_error()

        resolve = AsyncMock(return_value=primary)
        with (
            patch(
                "app.agent.skills.skill_failover.mark_unhealthy", new=AsyncMock()
            ) as p_mark,
            pytest.raises(openai.RateLimitError),
        ):
            await run_with_llm_failover(resolve, _run, task_key="market_daily_review")

        assert len(calls) == 1
        p_mark.assert_awaited_once_with(1)

    @pytest.mark.asyncio
    async def test_non_quota_error_propagates_without_retry(self) -> None:
        """非额度类异常（如 5xx/程序错误）不触发主备重试。"""
        primary = SimpleNamespace(config_id=1, model_name="m1")
        calls: list[object] = []

        async def _run(cfg: SimpleNamespace) -> str:
            calls.append(cfg)
            raise RuntimeError("connection reset")

        resolve = AsyncMock(return_value=primary)
        with (
            patch(
                "app.agent.skills.skill_failover.mark_unhealthy", new=AsyncMock()
            ) as p_mark,
            pytest.raises(RuntimeError),
        ):
            await run_with_llm_failover(resolve, _run, task_key="market_daily_review")

        assert len(calls) == 1
        p_mark.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_success_on_first_run_does_not_resolve_again(self) -> None:
        """首轮成功：不标记冷却，不重复解析配置。"""
        primary = SimpleNamespace(config_id=1, model_name="m1")
        resolve = AsyncMock(return_value=primary)
        with (
            patch(
                "app.agent.skills.skill_failover.mark_unhealthy", new=AsyncMock()
            ) as p_mark,
        ):
            result, cfg = await run_with_llm_failover(
                resolve, AsyncMock(return_value="ok"), task_key="market_daily_review"
            )

        assert result == "ok"
        assert cfg is primary
        resolve.assert_awaited_once()
        p_mark.assert_not_awaited()
