"""指数技术面服务契约测试（AI 综述技术分析输入构建）。"""

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.market import index_technical_service
from app.services.market.index_technical_service import TECH_CODES, build_technical_context

_TRADE_DATE = date(2026, 7, 17)  # 周五


def _daily_rows(
    closes: list[float],
    volumes: list[int],
    end_date: date = _TRADE_DATE,
    opens: list[float] | None = None,
) -> list[SimpleNamespace]:
    """构造升序 closes/volumes 对应的倒序 ORM 行（fetch_daily_bars 返回倒序）。"""
    rows = []
    for i, close in enumerate(closes):
        rows.append(
            SimpleNamespace(
                trade_date=end_date - timedelta(days=len(closes) - 1 - i),
                open=opens[i] if opens else close,
                high=close + 1,
                low=close - 1,
                close=close,
                volume=volumes[i],
            )
        )
    return list(reversed(rows))


def _minute_rows(day: date, count: int = 100, amount: float = 1e8) -> list[SimpleNamespace]:
    """构造 count 根分钟 K：前 10 根横盘，随后 40 根单边下跌，之后走平；全部为阴线。

    trade_time 按生产口径存 UTC（09:30 开盘 = 01:30 UTC）。
    """
    base = datetime(day.year, day.month, day.day, 1, 30, tzinfo=timezone.utc)
    rows = []
    for i in range(count):
        if i < 10:
            close = 100.0
        elif i < 50:
            close = float(100 - (i - 9))
        else:
            close = 60.0
        rows.append(
            SimpleNamespace(
                trade_time=base + timedelta(minutes=i),
                open=close + 1,
                close=close,
                amount=amount,
            )
        )
    return rows


def _patch_daily(rows: list[SimpleNamespace]) -> patch:
    return patch.object(
        index_technical_service,
        "fetch_daily_bars",
        AsyncMock(return_value=rows),
    )


def _big_bearish_rows() -> list[SimpleNamespace]:
    """100 根横盘 + 末根大阴线放量：跌破全部均线、创 20 日新低、放量、非地量。"""
    closes = [100.0] * 99 + [95.0]
    volumes = [1000] * 99 + [2000]
    opens = [100.0] * 100
    return _daily_rows(closes, volumes, opens=opens)


@pytest.mark.unit
class TestBuildTechnicalContextDaily:
    async def test_formats_daily_indicators(self) -> None:
        with _patch_daily(_big_bearish_rows()), patch.object(
            index_technical_service, "fetch_minute_bars", AsyncMock(return_value=[])
        ):
            output = await build_technical_context(MagicMock(), _TRADE_DATE)

        assert output.count("■") == len(TECH_CODES)
        assert "■ 沪指（sh000001）收 95.00（-5.00%）" in output
        assert "■ 富时A50（CN00Y）" in output
        assert "收大阴线（实体 -5.00%）" in output
        assert "跌破 MA10（99.50）" in output
        assert "跌破 MA30" in output
        assert "跌破 MA60" in output
        assert "创 20 日新低（前低 100.00）" in output
        assert "成交量为前 5 日均量的 2.00 倍（放量）" in output
        assert "20 日地量：否" in output
        assert "近 60 日前低支撑位 99.00" in output
        assert "跌破 周MA10" in output
        assert "周量能环比上周" in output

    async def test_low_volume_flags_floor_and_shrinkage(self) -> None:
        closes = [100.0] * 100
        volumes = [2000] * 99 + [1000]
        with _patch_daily(_daily_rows(closes, volumes)), patch.object(
            index_technical_service, "fetch_minute_bars", AsyncMock(return_value=[])
        ):
            output = await build_technical_context(MagicMock(), _TRADE_DATE)

        assert "成交量为前 5 日均量的 0.50 倍（缩量）" in output
        assert "20 日地量：是" in output
        assert "站上 MA10（100.00）" in output
        assert "未创 20 日新低" in output

    async def test_marks_stale_daily_data(self) -> None:
        rows = _daily_rows([100.0] * 100, [1000] * 100, end_date=date(2026, 7, 16))
        with _patch_daily(rows), patch.object(
            index_technical_service, "fetch_minute_bars", AsyncMock(return_value=[])
        ):
            output = await build_technical_context(MagicMock(), _TRADE_DATE)

        assert "［数据为最近交易日 2026-07-16］" in output

    async def test_no_daily_data(self) -> None:
        minute_mock = AsyncMock(return_value=[])
        with _patch_daily([]), patch.object(
            index_technical_service, "fetch_minute_bars", minute_mock
        ):
            output = await build_technical_context(MagicMock(), _TRADE_DATE)

        assert output.count("本地无日 K 数据") == len(TECH_CODES)
        minute_mock.assert_not_called()


@pytest.mark.unit
class TestBuildTechnicalContextIntraday:
    async def test_includes_intraday_structure_for_sh_index(self) -> None:
        today = _minute_rows(_TRADE_DATE)
        prev = _minute_rows(date(2026, 7, 16))
        minute_mock = AsyncMock(side_effect=[today, prev])
        with _patch_daily(_big_bearish_rows()), patch.object(
            index_technical_service, "fetch_minute_bars", minute_mock
        ):
            output = await build_technical_context(MagicMock(), _TRADE_DATE)

        assert minute_mock.await_count == 2
        assert "开盘 30 分钟成交 30 亿元（较前日同期 +0%）" in output
        assert "阴线分钟量能占比 100%" in output
        assert "尾盘 30 分钟量能占全天 30%" in output
        assert "最大跳水时段 09:49-10:19（-33.33%）" in output

    async def test_skips_intraday_when_minute_bars_insufficient(self) -> None:
        minute_mock = AsyncMock(
            side_effect=[
                _minute_rows(_TRADE_DATE, count=30),
                _minute_rows(date(2026, 7, 16), count=30),
            ]
        )
        with _patch_daily(_big_bearish_rows()), patch.object(
            index_technical_service, "fetch_minute_bars", minute_mock
        ):
            output = await build_technical_context(MagicMock(), _TRADE_DATE)

        assert "- 分时：" not in output

    async def test_intraday_only_for_sh_index(self) -> None:
        """非沪指标的不触发分钟线查询（仅 sh000001 两次：当日 + 前日）。"""
        minute_mock = AsyncMock(return_value=[])
        with _patch_daily(_big_bearish_rows()), patch.object(
            index_technical_service, "fetch_minute_bars", minute_mock
        ):
            await build_technical_context(MagicMock(), _TRADE_DATE)

        assert minute_mock.await_count == 2
        for call in minute_mock.await_args_list:
            assert call.args[1] == "sh000001"
