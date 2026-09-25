"""LLM 主备切换单测：错误分类、健康标记（redis fail-open）、解析健康门与 callback。"""

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


class TestClassify:
    def test_openai_rate_limit_hits(self) -> None:
        assert classify_llm_error(_openai_rate_limit()) is True

    def test_anthropic_429_and_402_hit(self) -> None:
        assert classify_llm_error(_anthropic_status_error(429, "rate limited")) is True
        assert classify_llm_error(_anthropic_status_error(402, "payment required")) is True

    def test_anthropic_5xx_misses(self) -> None:
        assert classify_llm_error(_anthropic_status_error(500, "internal server error")) is False

    def test_message_keywords_hit_without_status(self) -> None:
        assert classify_llm_error(RuntimeError("账户额度已用完")) is True
        assert classify_llm_error(RuntimeError("weekly usage limit exceeded")) is True
        assert classify_llm_error(RuntimeError("insufficient quota")) is True

    def test_validation_and_timeout_miss(self) -> None:
        assert classify_llm_error(ValueError("device returned an invalid schema")) is False
        assert classify_llm_error(RuntimeError("Request timed out")) is False

    def test_direct_failure_by_status_and_body(self) -> None:
        assert classify_llm_failure(429, "any") is True
        assert classify_llm_failure(None, "余额不足，请充值") is True
        assert classify_llm_failure(200, "quota exhausted") is True
        assert classify_llm_failure(503, "service unavailable") is False


class TestHealthMarks:
    async def test_mark_sets_cooldown_ttl(self) -> None:
        with patch.object(failover, "cache_set", new=AsyncMock()) as p_set:
            await mark_unhealthy(5)
        p_set.assert_awaited_once_with(
            "llm:health:5", "1", ex=failover.get_settings().llm_failover_cooldown_seconds
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
    def _primary(self, backup_config_id: int | None) -> Any:
        return SimpleNamespace(id=1, purpose="chat", backup_config_id=backup_config_id)

    async def test_switches_to_valid_backup(self) -> None:
        backup = SimpleNamespace(id=2, name="backup", purpose="chat", is_active=True)
        session = AsyncMock()
        session.get.return_value = backup
        with patch.object(failover, "is_unhealthy", new=AsyncMock(return_value=True)):
            result = await resolve_healthy(cast(AsyncSession, session), self._primary(2))
        assert result is backup

    async def test_keeps_primary_when_healthy(self) -> None:
        primary = self._primary(2)
        with patch.object(failover, "is_unhealthy", new=AsyncMock(return_value=False)):
            result = await resolve_healthy(cast(AsyncSession, AsyncMock()), primary)
        assert result is primary

    async def test_keeps_primary_without_backup(self) -> None:
        primary = self._primary(None)
        with patch.object(failover, "is_unhealthy", new=AsyncMock(return_value=True)):
            result = await resolve_healthy(cast(AsyncSession, AsyncMock()), primary)
        assert result is primary

    @pytest.mark.parametrize("backup", [None, SimpleNamespace(id=2, purpose="embedding", is_active=True),
                                        SimpleNamespace(id=2, purpose="chat", is_active=False)])
    async def test_invalid_backup_falls_back_to_primary(self, backup: Any) -> None:
        session = AsyncMock()
        session.get.return_value = backup
        with patch.object(failover, "is_unhealthy", new=AsyncMock(return_value=True)):
            result = await resolve_healthy(cast(AsyncSession, session), self._primary(2))
        assert result.id == 1


class TestFailoverHealthCallback:
    async def test_marks_on_classified_error(self) -> None:
        callback = FailoverHealthCallback(7)
        with patch.object(failover, "mark_unhealthy", new=AsyncMock()) as p_mark:
            await callback.on_llm_error(_openai_rate_limit())
        p_mark.assert_awaited_once_with(7)

    async def test_ignores_byok_and_unclassified(self) -> None:
        byok = FailoverHealthCallback(-5)
        normal = FailoverHealthCallback(7)
        with patch.object(failover, "mark_unhealthy", new=AsyncMock()) as p_mark:
            await byok.on_llm_error(_openai_rate_limit())
            await normal.on_llm_error(ValueError("bad output"))
        p_mark.assert_not_awaited()
