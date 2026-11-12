"""日 K 采集宇宙契约测试（自选股 ∪ Agent 生效选股/计划标的）。"""

import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from collector.spiders.kline_universe import fetch_kline_universe_codes


def _result(rows: list[tuple[str, ...]]) -> MagicMock:
    return MagicMock(all=MagicMock(return_value=rows))


@pytest.mark.unit
class TestKlineUniverse:
    @pytest.mark.asyncio
    async def test_unions_watchlist_selections_and_plans(self) -> None:
        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[
                _result([("000001",), ("600519",)]),
                _result([("002837",), ("000001",)]),
                _result([("688213",)]),
            ]
        )

        @contextlib.asynccontextmanager
        async def _cm():
            yield session

        def _fake_session_maker(*_args: object, **_kwargs: object):
            return lambda: _cm()

        with patch(
            "collector.spiders.kline_universe.async_sessionmaker", _fake_session_maker
        ):
            codes = await fetch_kline_universe_codes()

        assert codes == ["000001", "002837", "600519", "688213"]

    @pytest.mark.asyncio
    async def test_empty_universe_returns_empty(self) -> None:
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[_result([]), _result([]), _result([])])

        @contextlib.asynccontextmanager
        async def _cm():
            yield session

        def _fake_session_maker(*_args: object, **_kwargs: object):
            return lambda: _cm()

        with patch(
            "collector.spiders.kline_universe.async_sessionmaker", _fake_session_maker
        ):
            codes = await fetch_kline_universe_codes()

        assert codes == []
