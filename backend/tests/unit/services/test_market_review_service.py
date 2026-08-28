"""Unit tests for market review service (AI 复盘读写分离、多租户隔离与按分区编辑保存)。"""

from contextlib import asynccontextmanager
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.core.prompt_loader import PromptSection
from app.services import review as market_review_service
from app.services.review import market_review_generator
from app.services.review.market_review_service import (
    ReviewGenerationLockedError,
    ReviewNotFoundError,
    UnknownSectionError,
)

_TRADE_DATE = date(2026, 7, 17)
_CREATED_AT = datetime(2026, 7, 17, 16, 30, 0)
_USER_ID = 7

_SECTIONS = [
    PromptSection(key="overview", title="AI 大盘综述"),
    PromptSection(key="technical_analysis", title="技术面分析"),
    PromptSection(key="capital_analysis", title="资金面分析"),
    PromptSection(key="emotion_analysis", title="情绪与连板分析"),
    PromptSection(key="risk_advice", title="风险提示与策略建议"),
]


def _base_contents(**overrides: str) -> dict[str, str]:
    contents = {
        "overview": "总览",
        "technical_analysis": "技术",
        "capital_analysis": "资金",
        "emotion_analysis": "情绪",
        "risk_advice": "风险",
    }
    contents.update(overrides)
    return contents


def _structured(**overrides: str) -> dict:
    return {
        "trade_date": _TRADE_DATE.isoformat(),
        "sections": _base_contents(**overrides),
    }


def _base_row(structured: dict | None, row_id: int = 1) -> MagicMock:
    """ai_analysis_repository.load_latest_success 返回的 ORM 行。"""
    row = MagicMock()
    row.id = row_id
    row.structured_output = structured
    row.model = "openai/gpt-4o"
    row.created_at = _CREATED_AT
    return row


def _user_row(sections: dict[str, str] | None) -> MagicMock:
    """user_market_review_repository.find 返回的 ORM 行。"""
    row = MagicMock()
    row.sections = sections
    row.model = "openai/gpt-4o"
    row.generated_at = _CREATED_AT
    row.created_at = _CREATED_AT
    return row


def _contents_of(result: object) -> dict[str, str]:
    return {item.key: item.content for item in result.sections}  # type: ignore[attr-defined]


def _patch_stats() -> patch:
    return patch(
        "app.services.market_stats_service.get_market_stats",
        AsyncMock(return_value=SimpleNamespace(trade_date=_TRADE_DATE)),
    )


def _patch_trading_day(value: bool = True) -> patch:
    return patch(
        "app.services.trade_calendar_service.is_trading_day",
        AsyncMock(return_value=value),
    )


def _patch_prompt_config() -> patch:
    config = SimpleNamespace(sections=_SECTIONS)
    return patch.object(
        market_review_service,
        "load_prompt_config",
        lambda: config,
    )


def _patch_prompt_config_for_generate() -> patch:
    config = SimpleNamespace(sections=_SECTIONS)
    return patch.object(
        market_review_generator,
        "load_prompt_config",
        lambda: config,
    )


def _patch_redis_lock(acquired: bool = True) -> patch:
    @asynccontextmanager
    async def _fake_lock(*args: object, **kwargs: object):
        yield acquired

    return patch.object(market_review_generator, "redis_lock", _fake_lock)


@pytest.mark.unit
class TestGetMarketReview:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_cached_row(self) -> None:
        with (
            patch(
                "app.repositories.ai_analysis_repository.load_latest_success",
                AsyncMock(return_value=None),
            ),
            patch(
                "app.repositories.user_market_review_repository.find",
                AsyncMock(return_value=None),
            ),
            _patch_stats(),
            _patch_trading_day(),
            _patch_prompt_config(),
        ):
            result = await market_review_service.get_market_review(
                AsyncMock(), _USER_ID
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_merges_user_overlay_per_section(self) -> None:
        user_row = _user_row({"overview": "用户总览"})

        with (
            patch(
                "app.repositories.ai_analysis_repository.load_latest_success",
                AsyncMock(return_value=_base_row(_structured())),
            ),
            patch(
                "app.repositories.user_market_review_repository.find",
                AsyncMock(return_value=user_row),
            ),
            _patch_stats(),
            _patch_trading_day(),
            _patch_prompt_config(),
        ):
            result = await market_review_service.get_market_review(
                AsyncMock(), _USER_ID, _TRADE_DATE
            )

        assert result is not None
        assert result.trade_date == _TRADE_DATE
        contents = _contents_of(result)
        assert contents["overview"] == "用户总览"
        assert contents["capital_analysis"] == "资金"
        assert [item.title for item in result.sections] == [
            "AI 大盘综述",
            "技术面分析",
            "资金面分析",
            "情绪与连板分析",
            "风险提示与策略建议",
        ]
        assert result.cached is True
        assert result.edited is True

    @pytest.mark.asyncio
    async def test_falls_back_to_base_when_no_overlay(self) -> None:
        with (
            patch(
                "app.repositories.ai_analysis_repository.load_latest_success",
                AsyncMock(return_value=_base_row(_structured())),
            ),
            patch(
                "app.repositories.user_market_review_repository.find",
                AsyncMock(return_value=None),
            ),
            _patch_stats(),
            _patch_trading_day(),
            _patch_prompt_config(),
        ):
            result = await market_review_service.get_market_review(
                AsyncMock(), _USER_ID
            )

        assert result is not None
        assert _contents_of(result)["overview"] == "总览"
        assert result.cached is True
        assert result.edited is False


@pytest.mark.unit
class TestUpdateMarketReview:
    @pytest.mark.asyncio
    async def test_raises_when_no_existing_base(self) -> None:
        with (
            patch(
                "app.repositories.ai_analysis_repository.load_latest_success",
                AsyncMock(return_value=None),
            ),
            _patch_trading_day(),
            _patch_prompt_config(),
            pytest.raises(ReviewNotFoundError),
        ):
            await market_review_service.update_market_review(
                AsyncMock(), _USER_ID, _TRADE_DATE, "overview", "改后总览"
            )

    @pytest.mark.asyncio
    async def test_raises_when_section_unknown(self) -> None:
        upsert_mock = AsyncMock()
        with (
            patch(
                "app.repositories.user_market_review_repository.upsert_sections",
                upsert_mock,
            ),
            _patch_trading_day(),
            _patch_prompt_config(),
            pytest.raises(UnknownSectionError),
        ):
            await market_review_service.update_market_review(
                AsyncMock(), _USER_ID, _TRADE_DATE, "foo", "内容"
            )

        upsert_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_upserts_single_section_overlay(self) -> None:
        upsert_mock = AsyncMock()
        with (
            patch(
                "app.repositories.ai_analysis_repository.load_latest_success",
                AsyncMock(return_value=_base_row(_structured(), row_id=42)),
            ),
            patch(
                "app.repositories.user_market_review_repository.find",
                AsyncMock(return_value=None),
            ),
            patch(
                "app.repositories.user_market_review_repository.upsert_sections",
                upsert_mock,
            ),
            _patch_trading_day(),
            _patch_prompt_config(),
        ):
            result = await market_review_service.update_market_review(
                AsyncMock(), _USER_ID, _TRADE_DATE, "overview", "改后总览"
            )

        upsert_mock.assert_awaited_once()
        _, kwargs = upsert_mock.await_args
        assert kwargs["user_id"] == _USER_ID
        assert kwargs["base_review_id"] == 42
        stored = kwargs["sections"]
        assert stored["overview"] == "改后总览"
        assert stored["capital_analysis"] == "资金"

        assert result.trade_date == _TRADE_DATE
        contents = _contents_of(result)
        assert contents["overview"] == "改后总览"
        assert contents["risk_advice"] == "风险"
        assert result.cached is True
        assert result.edited is True
        assert result.generated_at == _CREATED_AT

    @pytest.mark.asyncio
    async def test_preserves_existing_user_sections(self) -> None:
        upsert_mock = AsyncMock()
        with (
            patch(
                "app.repositories.ai_analysis_repository.load_latest_success",
                AsyncMock(return_value=_base_row(_structured(), row_id=42)),
            ),
            patch(
                "app.repositories.user_market_review_repository.find",
                AsyncMock(return_value=_user_row({"risk_advice": "用户风险"})),
            ),
            patch(
                "app.repositories.user_market_review_repository.upsert_sections",
                upsert_mock,
            ),
            _patch_trading_day(),
            _patch_prompt_config(),
        ):
            result = await market_review_service.update_market_review(
                AsyncMock(), _USER_ID, _TRADE_DATE, "overview", "改后总览"
            )

        _, kwargs = upsert_mock.await_args
        stored = kwargs["sections"]
        assert stored["overview"] == "改后总览"
        assert stored["risk_advice"] == "用户风险"
        assert _contents_of(result)["risk_advice"] == "用户风险"


@pytest.mark.unit
class TestGenerateMarketReview:
    @pytest.mark.asyncio
    async def test_returns_cached_base_without_lock_when_exists(self) -> None:
        with (
            patch(
                "app.repositories.ai_analysis_repository.load_latest_success",
                AsyncMock(return_value=_base_row(_structured())),
            ),
            _patch_stats(),
            _patch_trading_day(),
            _patch_prompt_config_for_generate(),
        ):
            result = await market_review_service.generate_market_review(
                AsyncMock(), _TRADE_DATE
            )

        assert result.cached is True
        assert result.edited is False
        assert _contents_of(result)["overview"] == "总览"

    @pytest.mark.asyncio
    async def test_raises_when_lock_held_and_no_cache(self) -> None:
        with (
            patch(
                "app.repositories.ai_analysis_repository.load_latest_success",
                AsyncMock(return_value=None),
            ),
            _patch_stats(),
            _patch_trading_day(),
            _patch_prompt_config_for_generate(),
            _patch_redis_lock(acquired=False),
            pytest.raises(ReviewGenerationLockedError),
        ):
            await market_review_service.generate_market_review(AsyncMock(), _TRADE_DATE)


@pytest.mark.unit
class TestTradingDayGuard:
    @pytest.mark.asyncio
    async def test_get_market_review_rejects_non_trading_day(self) -> None:
        with (
            _patch_trading_day(False),
            pytest.raises(market_review_service.NonTradingDayError),
        ):
            await market_review_service.get_market_review(
                AsyncMock(), _USER_ID, _TRADE_DATE
            )

    @pytest.mark.asyncio
    async def test_generate_rejects_non_trading_day(self) -> None:
        with (
            _patch_trading_day(False),
            pytest.raises(market_review_service.NonTradingDayError),
        ):
            await market_review_service.generate_market_review(
                AsyncMock(), _TRADE_DATE
            )

    @pytest.mark.asyncio
    async def test_update_rejects_non_trading_day(self) -> None:
        with (
            _patch_trading_day(False),
            pytest.raises(market_review_service.NonTradingDayError),
        ):
            await market_review_service.update_market_review(
                AsyncMock(), _USER_ID, _TRADE_DATE, "overview", "内容"
            )
