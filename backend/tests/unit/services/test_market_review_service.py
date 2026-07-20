"""Unit tests for market review service (AI 复盘读写分离与编辑保存)。"""

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import market_review_service
from app.services.market_review_service import (
    MarketReviewContent,
    ReviewNotFoundError,
)

_TRADE_DATE = date(2026, 7, 17)
_CREATED_AT = datetime(2026, 7, 17, 16, 30, 0)


def _row(structured: dict | None, row_id: int = 1) -> dict:
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


@pytest.mark.unit
class TestGetCachedReview:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_cached_row(self) -> None:
        session = AsyncMock()
        session.execute.return_value = _execute_returning(None)

        with _patch_stats(), _patch_trading_day():
            result = await market_review_service.get_cached_review(session)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_cached_review_with_edited_flag(self) -> None:
        session = AsyncMock()
        session.execute.return_value = _execute_returning(
            _row(_structured(edited=True))
        )

        with _patch_stats(), _patch_trading_day():
            result = await market_review_service.get_cached_review(
                session, _TRADE_DATE
            )

        assert result is not None
        assert result.trade_date == _TRADE_DATE
        assert result.overview == "总览"
        assert result.cached is True
        assert result.edited is True
        assert result.model == "openai/gpt-4o"

    @pytest.mark.asyncio
    async def test_edited_defaults_false_for_llm_generated(self) -> None:
        session = AsyncMock()
        session.execute.return_value = _execute_returning(_row(_structured()))

        with _patch_stats(), _patch_trading_day():
            result = await market_review_service.get_cached_review(session)

        assert result is not None
        assert result.edited is False


@pytest.mark.unit
class TestUpdateMarketReview:
    @pytest.mark.asyncio
    async def test_raises_when_no_existing_review(self) -> None:
        session = AsyncMock()
        session.execute.return_value = _execute_returning(None)

        with _patch_trading_day(), pytest.raises(ReviewNotFoundError):
            await market_review_service.update_market_review(
                session,
                _TRADE_DATE,
                MarketReviewContent(
                    overview="a",
                    emotion_analysis="b",
                    capital_analysis="c",
                    risk_advice="d",
                ),
            )

    @pytest.mark.asyncio
    async def test_persists_edited_content(self) -> None:
        session = AsyncMock()
        session.execute.side_effect = [
            _execute_returning(_row(None, row_id=42)),
            MagicMock(),
        ]

        with _patch_trading_day():
            result = await market_review_service.update_market_review(
            session,
            _TRADE_DATE,
            MarketReviewContent(
                overview="改后总览",
                emotion_analysis="改后情绪",
                capital_analysis="改后资金",
                risk_advice="改后风险",
            ),
        )

        assert session.execute.await_count == 2
        update_params = session.execute.await_args_list[1].args[1]
        assert update_params["id"] == 42
        assert '"edited": true' in update_params["structured_output"]
        assert "改后总览" in update_params["structured_output"]
        session.commit.assert_awaited_once()

        assert result.trade_date == _TRADE_DATE
        assert result.overview == "改后总览"
        assert result.cached is True
        assert result.edited is True
        assert result.generated_at == _CREATED_AT


@pytest.mark.unit
class TestTradingDayGuard:
    @pytest.mark.asyncio
    async def test_get_cached_review_rejects_non_trading_day(self) -> None:
        session = AsyncMock()
        with (
            _patch_trading_day(False),
            pytest.raises(market_review_service.NonTradingDayError),
        ):
            await market_review_service.get_cached_review(session, _TRADE_DATE)

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
                _TRADE_DATE,
                MarketReviewContent(
                    overview="a",
                    emotion_analysis="b",
                    capital_analysis="c",
                    risk_advice="d",
                ),
            )
