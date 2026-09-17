"""情绪流读服务单测（复盘情绪输入：分布/净多空/样本不足标记）。"""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from app.services.social import feed_service

_TRADE_DATE = date(2026, 9, 17)


def _daily() -> dict[date, dict[str, int]]:
    return {
        date(2026, 9, 11): {"bullish": 4, "bearish": 2},
        date(2026, 9, 16): {"bullish": 6, "bearish": 1, "neutral": 1},
        _TRADE_DATE: {"bullish": 8, "bearish": 2, "neutral": 1},
    }


@pytest.mark.unit
class TestGetReviewSentiment:
    @pytest.mark.asyncio
    async def test_aggregates_counts_trend_and_top_stances(self) -> None:
        top = [
            {
                "alias": "大V甲",
                "category": "finance_kol",
                "stance": "bullish",
                "confidence": 0.9,
                "summary": "看多",
                "core_arguments": ["放量突破"],
            }
        ]
        with (
            patch.object(
                feed_service.post_repository,
                "daily_stance_overview",
                AsyncMock(return_value=_daily()),
            ),
            patch.object(
                feed_service.post_repository, "top_stances", AsyncMock(return_value=top)
            ),
            patch.object(
                feed_service.post_repository,
                "count_day_active_accounts",
                AsyncMock(return_value=5),
            ),
        ):
            result = await feed_service.get_review_sentiment(None, _TRADE_DATE)

        assert result["trade_date"] == "2026-09-17"
        assert result["counts"] == {"bullish": 8, "bearish": 2, "neutral": 1}
        assert result["net_bullish"] == 6
        assert result["total"] == 11
        assert result["active_accounts"] == 5
        assert result["sample_insufficient"] is False
        assert [row["date"] for row in result["daily_trend"]] == [
            "2026-09-11",
            "2026-09-16",
            "2026-09-17",
        ]
        assert result["daily_trend"][-1]["net_bullish"] == 6
        assert result["top_stances"] == top
        assert "反向指标" in result["note"]

    @pytest.mark.asyncio
    async def test_flags_insufficient_sample(self) -> None:
        with (
            patch.object(
                feed_service.post_repository,
                "daily_stance_overview",
                AsyncMock(return_value={_TRADE_DATE: {"bullish": 1}}),
            ),
            patch.object(
                feed_service.post_repository, "top_stances", AsyncMock(return_value=[])
            ),
            patch.object(
                feed_service.post_repository,
                "count_day_active_accounts",
                AsyncMock(return_value=1),
            ),
        ):
            result = await feed_service.get_review_sentiment(None, _TRADE_DATE)

        assert result["total"] == 1
        assert result["sample_insufficient"] is True
        assert "不足" in result["note"]

    @pytest.mark.asyncio
    async def test_empty_day_defaults_to_zero_counts(self) -> None:
        with (
            patch.object(
                feed_service.post_repository,
                "daily_stance_overview",
                AsyncMock(return_value={}),
            ),
            patch.object(
                feed_service.post_repository, "top_stances", AsyncMock(return_value=[])
            ),
            patch.object(
                feed_service.post_repository,
                "count_day_active_accounts",
                AsyncMock(return_value=0),
            ),
        ):
            result = await feed_service.get_review_sentiment(None, _TRADE_DATE)

        assert result["counts"] == {"bullish": 0, "bearish": 0, "neutral": 0}
        assert result["net_bullish"] == 0
        assert result["sample_insufficient"] is True

