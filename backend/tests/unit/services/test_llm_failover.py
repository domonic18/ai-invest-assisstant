"""LLM 主备切换单测：失败分类（quota/connect/None）、两档冷却标记（redis fail-open）、健康门与 callback。"""

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import anthropic
import httpx
import openai
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.admin import llm_failover as failover
from app.services.admin.llm_failover import (
    FailoverHealthCallback,
    classify_llm_error,
    classify_llm_failure,
    clear_unhealthy,
    degraded_until,
    is_unhealthy,
    mark_unhealthy,
    resolve_healthy,
)

pytestmark = pytest.mark.unit


def _openai_rate_limit(status: int = 429, message: str = "Rate limit reached") -> openai.RateLimitError:
    request = httpx.Request("POST", "https://api.example.com/v1/chat/completions")
    return openai.RateLimitError(message, response=httpx.Response(status_code=status, request=request), body=None)


def _anthropic_status_error(status: int, message: str) -> anthropic.APIStatusError:
    request = httpx.Request("POST", "https://api.example.com/v1/messages")
    return anthropic.APIStatusError(message, response=httpx.Response(status_code=status, request=request), body=None)


def _openai_timeout() -> openai.APITimeoutError:
    return openai.APITimeoutError(request=httpx.Request("POST", "https://api.example.com/v1/chat/completions"))


class TestClassify:
    def test_openai_rate_limit_hits(self) -> None:
        assert classify_llm_error(_openai_rate_limit()) == "quota"

    def test_anthropic_429_and_402_hit(self) -> None:
        assert classify_llm_error(_anthropic_status_error(429, "rate limited")) == "quota"
        assert classify_llm_error(_anthropic_status_error(402, "payment required")) == "quota"

    def test_anthropic_5xx_misses(self) -> None:
        assert classify_llm_error(_anthropic_status_error(500, "internal server error")) is None

    def test_message_keywords_hit_without_status(self) -> None:
        assert classify_llm_error(RuntimeError("账户额度已用完")) == "quota"
        assert classify_llm_error(RuntimeError("weekly usage limit exceeded")) == "quota"
        assert classify_llm_error(RuntimeError("insufficient quota")) == "quota"

    def test_sdk_timeout_is_connect(self) -> None:
        """连接类失败（超时/断流）纳入切备触发：SDK 异常类型优先识别。"""
        assert classify_llm_error(_openai_timeout()) == "connect"
        assert classify_llm_error(httpx.RemoteProtocolError("peer closed connection")) == "connect"

    def test_timeout_text_falls_to_connect(self) -> None:
        """非 SDK 异常的连接类文案兜底（2026-11-10 生产 mimo 断流场景）。"""
        assert classify_llm_error(RuntimeError("Request timed out")) == "connect"
        assert classify_llm_error(RuntimeError("stream disconnected")) == "connect"
        assert classify_llm_error(RuntimeError("connection reset by peer")) == "connect"

    def test_validation_misses(self) -> None:
        assert classify_llm_error(ValueError("device returned an invalid schema")) is None

    def test_direct_failure_by_status_and_body(self) -> None:
        assert classify_llm_failure(429, "any") == "quota"
        assert classify_llm_failure(None, "余额不足，请充值") == "quota"
        assert classify_llm_failure(200, "quota exhausted") == "quota"
        assert classify_llm_failure(None, "read timeout") == "connect"
        assert classify_llm_failure(503, "service unavailable") is None


class TestHealthMarks:
    async def test_mark_sets_quota_cooldown_by_default(self) -> None:
        with patch.object(failover, "cache_set", new=AsyncMock()) as p_set:
            await mark_unhealthy(5)
        p_set.assert_awaited_once_with(
            "llm:health:5", "1", ex=failover.get_settings().llm_failover_cooldown_seconds
        )

    async def test_mark_sets_short_cooldown_for_connect(self) -> None:
        """connect 类短冷却（瞬时抖动不长罚），quota/None 走长冷却。"""
        with patch.object(failover, "cache_set", new=AsyncMock()) as p_set:
            await mark_unhealthy(5, failure_class="connect")
        p_set.assert_awaited_once_with(
            "llm:health:5",
            "1",
            ex=failover.get_settings().llm_failover_connect_cooldown_seconds,
        )
        assert (
            failover.get_settings().llm_failover_connect_cooldown_seconds
            < failover.get_settings().llm_failover_cooldown_seconds
        )

    async def test_mark_ignores_byok_sentinel_id(self) -> None:
        with patch.object(failover, "cache_set", new=AsyncMock()) as p_set:
            await mark_unhealthy(-3)
        p_set.assert_not_awaited()

    async def test_clear_and_is_unhealthy(self) -> None:
        with (
            patch.object(failover, "cache_delete", new=AsyncMock()) as p_del,
            patch.object(failover, "cache_exists", new=AsyncMock(return_value=True)),
        ):
            await clear_unhealthy(7)
            assert await is_unhealthy(7) is True
        p_del.assert_awaited_once_with("llm:health:7")

    async def test_degraded_until_from_ttl(self) -> None:
        with patch.object(failover, "cache_ttl", new=AsyncMock(return_value=300)):
            until = await degraded_until(7)
        assert until is not None

    async def test_degraded_until_none_without_mark(self) -> None:
        with patch.object(failover, "cache_ttl", new=AsyncMock(return_value=-2)):
            assert await degraded_until(7) is None


class TestResolveHealthy:
    def _primary(self) -> Any:
        return SimpleNamespace(id=1, purpose="chat")

    async def test_switches_to_valid_backup(self) -> None:
        """主冷却期内切显式备用（备用来自选择点，不再读主条目列）。"""
        backup = SimpleNamespace(id=2, name="backup", purpose="chat", is_active=True)
        session = AsyncMock()
        session.get.return_value = backup
        with patch.object(failover, "is_unhealthy", new=AsyncMock(return_value=True)):
            result = await resolve_healthy(
                cast(AsyncSession, session), self._primary(), 2
            )
        assert result is backup

    async def test_keeps_primary_when_healthy(self) -> None:
        primary = self._primary()
        with patch.object(failover, "is_unhealthy", new=AsyncMock(return_value=False)):
            result = await resolve_healthy(cast(AsyncSession, AsyncMock()), primary, 2)
        assert result is primary

    async def test_keeps_primary_without_backup(self) -> None:
        primary = self._primary()
        with patch.object(failover, "is_unhealthy", new=AsyncMock(return_value=True)):
            result = await resolve_healthy(cast(AsyncSession, AsyncMock()), primary, None)
        assert result is primary

    @pytest.mark.parametrize("backup", [None, SimpleNamespace(id=2, purpose="embedding", is_active=True),
                                        SimpleNamespace(id=2, purpose="chat", is_active=False),
                                        SimpleNamespace(id=1, purpose="chat", is_active=True)])
    async def test_invalid_backup_falls_back_to_primary(self, backup: Any) -> None:
        """备用失配（不存在/停用/用途不一致/与主同 id）：维持主配置并告警。"""
        session = AsyncMock()
        session.get.return_value = backup
        with patch.object(failover, "is_unhealthy", new=AsyncMock(return_value=True)):
            result = await resolve_healthy(cast(AsyncSession, session), self._primary(), 2)
        assert result.id == 1


class TestFailoverHealthCallback:
    async def test_marks_quota_with_tier(self) -> None:
        callback = FailoverHealthCallback(7)
        with patch.object(failover, "mark_unhealthy", new=AsyncMock()) as p_mark:
            await callback.on_llm_error(_openai_rate_limit())
        p_mark.assert_awaited_once_with(7, failure_class="quota")

    async def test_marks_connect_with_tier(self) -> None:
        callback = FailoverHealthCallback(7)
        with patch.object(failover, "mark_unhealthy", new=AsyncMock()) as p_mark:
            await callback.on_llm_error(_openai_timeout())
        p_mark.assert_awaited_once_with(7, failure_class="connect")

    async def test_ignores_byok_and_unclassified(self) -> None:
        byok = FailoverHealthCallback(-5)
        normal = FailoverHealthCallback(7)
        with patch.object(failover, "mark_unhealthy", new=AsyncMock()) as p_mark:
            await byok.on_llm_error(_openai_rate_limit())
            await normal.on_llm_error(ValueError("bad output"))
        p_mark.assert_not_awaited()
