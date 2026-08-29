"""涨停 AI 归因采集器契约测试（交易日跳过/生成/缓存命中/数据未就绪传播）。"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.review import ReviewInputDataNotReadyError
from collector.core.base import CollectStatus
from collector.spiders.limit_up_ai_review import LimitUpAiReviewCollector

_TRADE_DATE = date(2026, 7, 17)


def _patches(cached, generate_side_effect=None):
    """公共 patch 组：交易日/日历/会话/服务层缓存与生成。"""
    session_factory = patch(
        "collector.spiders.limit_up_ai_review.AsyncSessionLocal"
    )
    return (
        patch(
            "collector.spiders.limit_up_ai_review.is_trading_day",
            return_value=True,
        ),
        patch(
            "collector.spiders.limit_up_ai_review.latest_trading_day",
            return_value=_TRADE_DATE,
        ),
        session_factory,
        patch(
            "collector.spiders.limit_up_ai_review.limit_up_ai_service.get_cached_attribution",
            AsyncMock(return_value=cached),
        ),
        patch(
            "collector.spiders.limit_up_ai_review.limit_up_ai_service.generate_attribution",
            AsyncMock(side_effect=generate_side_effect) if generate_side_effect else AsyncMock(),
        ),
    )


@pytest.mark.unit
class TestLimitUpAiReviewCollector:
    @pytest.mark.asyncio
    async def test_skips_non_trading_day(self) -> None:
        collector = LimitUpAiReviewCollector(
            {"source": "internal", "data_type": "ai_limit_up_review"}
        )

        with (
            patch(
                "collector.spiders.limit_up_ai_review.is_trading_day",
                return_value=False,
            ),
            patch(
                "collector.spiders.limit_up_ai_review.latest_trading_day",
                return_value=_TRADE_DATE,
            ),
        ):
            result = await collector.run()

        assert result.status == CollectStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_success_when_generates_new_attribution(self) -> None:
        collector = LimitUpAiReviewCollector(
            {"source": "internal", "data_type": "ai_limit_up_review"}
        )
        trading_day, latest, session_factory, get_cached, generate = _patches(None)

        with (
            trading_day,
            latest,
            session_factory as mock_factory,
            get_cached,
            generate as generate_mock,
        ):
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await collector.run()

        assert result.status == CollectStatus.SUCCESS
        assert result.items_stored == 1
        assert result.metadata["trade_date"] == _TRADE_DATE.isoformat()
        assert result.metadata["cached"] is False
        generate_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skipped_when_attribution_already_cached(self) -> None:
        collector = LimitUpAiReviewCollector(
            {"source": "internal", "data_type": "ai_limit_up_review"}
        )
        trading_day, latest, session_factory, get_cached, generate = _patches(
            cached=MagicMock()
        )

        with (
            trading_day,
            latest,
            session_factory as mock_factory,
            get_cached,
            generate as generate_mock,
        ):
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await collector.run()

        assert result.status == CollectStatus.SKIPPED
        assert result.items_stored == 0
        assert result.metadata["cached"] is True
        generate_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_not_ready_error_propagates(self) -> None:
        """数据未就绪异常必须向上传播，由 Celery 任务重试，而非转为 FAILED 结果。"""
        collector = LimitUpAiReviewCollector(
            {"source": "internal", "data_type": "ai_limit_up_review"}
        )
        trading_day, latest, session_factory, get_cached, generate = _patches(
            None, generate_side_effect=ReviewInputDataNotReadyError()
        )

        with (
            trading_day,
            latest,
            session_factory as mock_factory,
            get_cached,
            generate,
        ):
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            with pytest.raises(ReviewInputDataNotReadyError):
                await collector.run()
