"""用户自加 A 股跟踪标的：ETF/指数路由与采集缺省范围测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from collector.spiders.tracked_a_share import fetch_tracked_extra_codes, is_etf_code


@pytest.mark.unit
class TestIsEtfCode:
    @pytest.mark.parametrize(
        ("code", "expected"),
        [
            ("sh510300", True),
            ("sh588090", True),
            ("sz159915", True),
            ("sz161725", True),
            ("sh000905", False),
            ("sh000688", False),
            ("sz399006", False),
        ],
    )
    def test_prefix_routing(self, code: str, expected: bool) -> None:
        assert is_etf_code(code) is expected


@pytest.mark.unit
class TestFetchTrackedExtraCodes:
    @pytest.mark.asyncio
    async def test_excludes_fixed_and_disabled(self) -> None:
        rows = [
            ("sh000001",),  # 固定展示，排除
            ("sh000905",),
            ("sh510500",),
            ("CN00Y",),  # 固定展示，排除
        ]
        session = MagicMock()
        session.execute = AsyncMock(
            return_value=MagicMock(all=MagicMock(return_value=rows))
        )
        session_maker = MagicMock()
        session_maker.return_value.__aenter__ = AsyncMock(return_value=session)
        session_maker.return_value.__aexit__ = AsyncMock(return_value=None)

        with (
            patch(
                "collector.spiders.tracked_a_share.get_engine", MagicMock()
            ),
            patch(
                "collector.spiders.tracked_a_share.async_sessionmaker",
                return_value=session_maker,
            ),
        ):
            codes = await fetch_tracked_extra_codes()

        assert codes == ["sh000905", "sh510500"]
