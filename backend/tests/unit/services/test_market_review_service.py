"""Unit tests for market review service (AI 复盘读写分离、多租户隔离与编辑保存)。"""

from contextlib import asynccontextmanager
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import market_review_service
from app.services.market_review_service import (
    MarketReviewContent,
    ReviewGenerationLockedError,
    ReviewNotFoundError,
)

_TRADE_DATE = date(2026, 7, 17)
_CREATED_AT = datetime(2026, 7, 17, 16, 30, 0)
_USER_ID = 7


def _base_row(structured: dict | None, row_id: int = 1) -> dict:
    return {
        "id": row_id,
        "structured_output": structured,
        "model": "openai/gpt-4o",
        "created_at": _CREATED_AT,
    }


def _execute_returning(row: dict | None) -> MagicMock:
    return MagicMock(mappings=lambda: MagicMock(first=lambda: row))


def _structured(edited: bool = False) -> dict:
    data = {
        "trade_date": _TRADE_DATE.isoformat(),
        "overview": "总览",
        "emotion_analysis": "情绪",
        "capital_analysis": "资金",
        "risk_advice": "风险",
    }
    if edited:
        data["edited"] = True
    return data


def _patch_stats() -> patch:
    return patch.object(
        market_review_service.market_service,
        "get_market_stats",
        AsyncMock(return_value=SimpleNamespace(trade_date=_TRADE_DATE)),
    )


def _patch_trading_day(value: bool = True) -> patch:
    return patch.object(
        market_review_service.market_service,
        "is_trading_day",
        AsyncMock(return_value=value),
    )


def _patch_redis_lock(acquired: bool = True) -> patch:
    @asynccontextmanager
    async def _fake_lock(*args: object, **kwargs: object):
        yield acquired

    return patch.object(market_review_service, "redis_lock", _fake_lock)


@pytest.mark.unit
class TestGetMarketReview:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_cached_row(self) -> None:
        session = AsyncMock()
        session.execute.return_value = _execute_returning(None)

        with _patch_stats(), _patch_trading_day():
            result = await market_review_service.get_market_review(
                session, _USER_ID
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_user_edit_when_overlay_exists(self) -> None:
        session = AsyncMock()
        session.execute.return_value = _execute_returning(
            {
                "overview": "用户总览",
                "emotion_analysis": "用户情绪",
                "capital_analysis": "用户资金",
                "risk_advice": "用户风险",
                "model": "openai/gpt-4o",
                "generated_at": _CREATED_AT,
                "created_at": _CREATED_AT,
            }
        )

        with _patch_stats(), _patch_trading_day():
            result = await market_review_service.get_market_review(
                session, _USER_ID, _TRADE_DATE
            )

        assert result is not None
        assert result.trade_date == _TRADE_DATE
        assert result.overview == "用户总览"
        assert result.cached is True
        assert result.edited is True

    @pytest.mark.asyncio
    async def test_falls_back_to_base_when_no_overlay(self) -> None:
        session = AsyncMock()
        session.execute.side_effect = [
            _execute_returning(None),  # user edit
            _execute_returning(_base_row(_structured())),  # base
        ]

        with _patch_stats(), _patch_trading_day():
            result = await market_review_service.get_market_review(
                session, _USER_ID
            )

        assert result is not None
        assert result.overview == "总览"
        assert result.cached is True
        assert result.edited is False


@pytest.mark.unit
class TestUpdateMarketReview:
    @pytest.mark.asyncio
    async def test_raises_when_no_existing_base(self) -> None:
        session = AsyncMock()
        session.execute.return_value = _execute_returning(None)

        with _patch_trading_day(), pytest.raises(ReviewNotFoundError):
            await market_review_service.update_market_review(
                session,
                _USER_ID,
                _TRADE_DATE,
                MarketReviewContent(
                    overview="a",
                    emotion_analysis="b",
                    capital_analysis="c",
                    risk_advice="d",
                ),
            )

    @pytest.mark.asyncio
    async def test_upserts_user_overlay(self) -> None:
        session = AsyncMock()
        session.execute.side_effect = [
            _execute_returning(_base_row(_structured(), row_id=42)),
            MagicMock(),
        ]

        with _patch_trading_day():
            result = await market_review_service.update_market_review(
                session,
                _USER_ID,
                _TRADE_DATE,
                MarketReviewContent(
                    overview="改后总览",
                    emotion_analysis="改后情绪",
                    capital_analysis="改后资金",
                    risk_advice="改后风险",
                ),
            )

        assert session.execute.await_count == 2
        upsert_params = session.execute.await_args_list[1].args[1]
        assert upsert_params["user_id"] == _USER_ID
        assert upsert_params["base_review_id"] == 42
        assert upsert_params["overview"] == "改后总览"
        session.commit.assert_awaited_once()

        assert result.trade_date == _TRADE_DATE
        assert result.overview == "改后总览"
        assert result.cached is True
        assert result.edited is True
        assert result.generated_at == _CREATED_AT


@pytest.mark.unit
class TestGenerateMarketReview:
    @pytest.mark.asyncio
    async def test_returns_cached_base_without_lock_when_exists(self) -> None:
        session = AsyncMock()
        session.execute.return_value = _execute_returning(
            _base_row(_structured())
        )

        with _patch_stats(), _patch_trading_day():
            result = await market_review_service.generate_market_review(
                session, _TRADE_DATE
            )

        assert result.cached is True
        assert result.edited is False
        assert result.overview == "总览"

    @pytest.mark.asyncio
    async def test_raises_when_lock_held_and_no_cache(self) -> None:
        session = AsyncMock()
        session.execute.return_value = _execute_returning(None)

        with (
            _patch_stats(),
            _patch_trading_day(),
            _patch_redis_lock(acquired=False),
            pytest.raises(ReviewGenerationLockedError),
        ):
            await market_review_service.generate_market_review(session, _TRADE_DATE)


@pytest.mark.unit
class TestTradingDayGuard:
    @pytest.mark.asyncio
    async def test_get_market_review_rejects_non_trading_day(self) -> None:
        session = AsyncMock()
        with (
            _patch_trading_day(False),
            pytest.raises(market_review_service.NonTradingDayError),
        ):
            await market_review_service.get_market_review(
                session, _USER_ID, _TRADE_DATE
            )

    @pytest.mark.asyncio
    async def test_generate_rejects_non_trading_day(self) -> None:
        session = AsyncMock()
        with (
            _patch_trading_day(False),
            pytest.raises(market_review_service.NonTradingDayError),
        ):
            await market_review_service.generate_market_review(
                session, _TRADE_DATE
            )

    @pytest.mark.asyncio
    async def test_update_rejects_non_trading_day(self) -> None:
        session = AsyncMock()
        with (
            _patch_trading_day(False),
            pytest.raises(market_review_service.NonTradingDayError),
        ):
            await market_review_service.update_market_review(
                session,
                _USER_ID,
                _TRADE_DATE,
                MarketReviewContent(
                    overview="a",
                    emotion_analysis="b",
                    capital_analysis="c",
                    risk_advice="d",
                ),
            )
