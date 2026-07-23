"""Unit tests for market daily review collector."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from collector.core.base import CollectStatus
from collector.spiders.market_daily_review import MarketDailyReviewCollector

_TRADE_DATE = date(2026, 7, 17)


@pytest.mark.unit
class TestMarketDailyReviewCollector:
    @pytest.mark.asyncio
    async def test_skips_non_trading_day(self) -> None:
        collector = MarketDailyReviewCollector({"source": "internal", "data_type": "ai_market_daily_review"})

        with patch(
            "collector.spiders.market_daily_review.is_trading_day",
            return_value=False,
        ), patch(
            "collector.spiders.market_daily_review.latest_trading_day",
            return_value=_TRADE_DATE,
        ):
            result = await collector.run()

        assert result.status == CollectStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_success_when_generates_new_review(self) -> None:
        collector = MarketDailyReviewCollector({"source": "internal", "data_type": "ai_market_daily_review"})
        mock_review = MagicMock(
            cached=False,
        )

        with (
            patch(
                "collector.spiders.market_daily_review.is_trading_day",
                return_value=True,
            ),
            patch(
                "collector.spiders.market_daily_review.latest_trading_day",
                return_value=_TRADE_DATE,
            ),
            patch(
                "collector.spiders.market_daily_review.AsyncSessionLocal"
            ) as mock_session_factory,
            patch(
                "collector.spiders.market_daily_review.market_review_service.generate_market_review",
                AsyncMock(return_value=mock_review),
            ),
        ):
            mock_session = AsyncMock()
            mock_session_factory.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_session_factory.return_value.__aexit__ = AsyncMock(
                return_value=False
            )
            result = await collector.run()

        assert result.status == CollectStatus.SUCCESS
        assert result.items_stored == 1
        assert result.metadata["trade_date"] == _TRADE_DATE.isoformat()

    @pytest.mark.asyncio
    async def test_skipped_when_review_already_cached(self) -> None:
        collector = MarketDailyReviewCollector({"source": "internal", "data_type": "ai_market_daily_review"})
        mock_review = MagicMock(cached=True)

        with (
            patch(
                "collector.spiders.market_daily_review.is_trading_day",
                return_value=True,
            ),
            patch(
                "collector.spiders.market_daily_review.latest_trading_day",
                return_value=_TRADE_DATE,
            ),
            patch(
                "collector.spiders.market_daily_review.AsyncSessionLocal"
            ) as mock_session_factory,
            patch(
                "collector.spiders.market_daily_review.market_review_service.generate_market_review",
                AsyncMock(return_value=mock_review),
            ),
        ):
            mock_session = AsyncMock()
            mock_session_factory.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_session_factory.return_value.__aexit__ = AsyncMock(
                return_value=False
            )
            result = await collector.run()

        assert result.status == CollectStatus.SKIPPED
        assert result.items_stored == 0
