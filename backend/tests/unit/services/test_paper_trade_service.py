"""模拟盘盘后同步服务测试（规范化 / 幂等 upsert / 锁与未配置语义）。"""

from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import ConflictError
from app.services.trading import paper_trade_service as svc
from app.services.trading.errors import (
    PaperTradeGatewayError,
    PaperTradeNotConfiguredError,
)

_TRADE_DATE = date(2026, 9, 24)


def _lock(acquired: bool = True):
    @asynccontextmanager
    async def _fake(key: str, ttl: int = 300):
        yield acquired

    return _fake


@pytest.mark.unit
class TestNormalizeHelpers:
    def test_stock_code_strips_prefix(self) -> None:
        assert svc._stock_code("SHSE.600000") == "600000"
        assert svc._stock_code("600000") == "600000"

    def test_counter_datetime_epoch_seconds_and_ms(self) -> None:
        expected = datetime(2026, 9, 24, 8, 0, tzinfo=timezone.utc)
        assert svc._counter_datetime(1_790_236_800) == expected
        assert svc._counter_datetime(1_790_236_800_000) == expected

    def test_counter_datetime_iso_variants(self) -> None:
        assert svc._counter_datetime("2026-09-24T16:05:00+08:00") == datetime(
            2026, 9, 24, 8, 5, tzinfo=timezone.utc
        )
        # naive ISO 视作 UTC（兜底，不抛错）
        assert svc._counter_datetime("2026-09-24T08:00:00") == datetime(
            2026, 9, 24, 8, 0, tzinfo=timezone.utc
        )
        assert svc._counter_datetime("not-a-date") is None
        assert svc._counter_datetime("") is None
        assert svc._counter_datetime(None) is None

    def test_cn_trade_date_crosses_midnight(self) -> None:
        # UTC 24 日 16:05 = CN 25 日 00:05，业务日归 25 日
        dt = datetime(2026, 9, 24, 16, 5, tzinfo=timezone.utc)
        assert svc._cn_trade_date(dt, _TRADE_DATE) == date(2026, 9, 25)
        assert svc._cn_trade_date(None, _TRADE_DATE) == _TRADE_DATE

    def test_normalize_orders_skips_missing_cl_ord_id(self) -> None:
        raw = [
            {
                "cl_ord_id": "o1",
                "symbol": "SHSE.600000",
                "side": 1,
                "order_type": 1,
                "price": "12.34",
                "volume": 100,
                "status": 3,
                "created_at": "2026-09-24T01:15:00Z",
            },
            {"symbol": "SHSE.600000"},  # 缺 cl_ord_id → 跳过
        ]
        rows = svc._normalize_orders(raw, _TRADE_DATE)

        assert len(rows) == 1
        row = rows[0]
        assert row["cl_ord_id"] == "o1"
        assert row["trade_date"] == _TRADE_DATE
        assert row["stock_code"] == "600000"
        assert row["price"] == Decimal("12.34")
        assert row["raw"] == raw[0]

    def test_normalize_executions_id_fallback_and_skip(self) -> None:
        created = "2026-09-24T03:00:00Z"
        raw = [
            {"ex_exec_id": "e1", "cl_ord_id": "o1", "symbol": "SZSE.000001"},
            # 缺 ex_exec_id → 组合键回退
            {
                "cl_ord_id": "o2",
                "symbol": "SZSE.000001",
                "created_at": created,
            },
            # 键与回退依据全缺 → 跳过
            {"symbol": "SZSE.000001"},
        ]
        rows = svc._normalize_executions(raw, _TRADE_DATE)

        assert len(rows) == 2
        assert rows[0]["exec_id"] == "e1"
        assert rows[1]["exec_id"] == f"o2:{datetime(2026, 9, 24, 3, 0, tzinfo=timezone.utc).isoformat()}"
        assert rows[1]["trade_date"] == _TRADE_DATE

    def test_normalize_cash_ignores_non_dict(self) -> None:
        row = svc._normalize_cash([], _TRADE_DATE)
        assert row["trade_date"] == _TRADE_DATE
        assert row["nav"] is None

        row = svc._normalize_cash({"nav": "123456.78", "available": 1000}, _TRADE_DATE)
        assert row["nav"] == Decimal("123456.78")
        assert row["available"] == Decimal("1000")

    def test_normalize_cash_unwraps_counter_list(self) -> None:
        # 实测柜台对单个 cash 对象也包数组返回
        row = svc._normalize_cash(
            [{"nav": 200000, "available": 200000, "balance": 200000}], _TRADE_DATE
        )
        assert row["nav"] == Decimal("200000")
        assert row["trade_date"] == _TRADE_DATE


def _settings(url: str = "http://paper-trade:8020") -> SimpleNamespace:
    return SimpleNamespace(paper_trade_url=url, paper_trade_timeout=1.0)


def _client_mock(
    orders: list[dict], executions: list[dict], cash: dict
) -> MagicMock:
    client = MagicMock()
    client.get_intraday_orders = AsyncMock(return_value=orders)
    client.get_intraday_executions = AsyncMock(return_value=executions)
    client.get_cash = AsyncMock(return_value=cash)
    return client


@pytest.mark.unit
class TestSyncDaily:
    @pytest.mark.asyncio
    async def test_raises_when_not_configured(self) -> None:
        session = AsyncMock()
        with patch.object(svc, "get_settings", lambda: _settings(url="")):
            with pytest.raises(PaperTradeNotConfiguredError):
                await svc.sync_daily(session, _TRADE_DATE)
        session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_happy_path_upserts_three_tables(self) -> None:
        session = AsyncMock()
        orders = [{"cl_ord_id": "o1", "symbol": "SHSE.600000", "status": 3}]
        executions = [{"ex_exec_id": "e1", "cl_ord_id": "o1"}]
        cash = {"nav": "100000.00"}

        with (
            patch.object(svc, "get_settings", lambda: _settings()),
            patch.object(svc, "redis_lock", _lock(True)),
            patch.object(svc, "PaperTradeClient", lambda url: _client_mock(orders, executions, cash)),
        ):
            summary = await svc.sync_daily(session, _TRADE_DATE)

        assert summary == {
            "trade_date": _TRADE_DATE.isoformat(),
            "orders": 1,
            "executions": 1,
            "nav": 100000.0,
        }
        # 委托 upsert + 回报插入 + 资金快照 upsert = 3 次写，随后统一 commit
        assert session.execute.await_count == 3
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_empty_counter_payloads_commit_snapshot_only(self) -> None:
        session = AsyncMock()

        with (
            patch.object(svc, "get_settings", lambda: _settings()),
            patch.object(svc, "redis_lock", _lock(True)),
            patch.object(svc, "PaperTradeClient", lambda url: _client_mock([], [], {})),
        ):
            summary = await svc.sync_daily(session, _TRADE_DATE)

        assert summary["orders"] == 0
        assert summary["executions"] == 0
        # 空委托/回报跳过写库，资金快照仍必须落（净值曲线连续性）
        assert session.execute.await_count == 1
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_lock_not_acquired_raises_conflict(self) -> None:
        session = AsyncMock()
        with (
            patch.object(svc, "get_settings", lambda: _settings()),
            patch.object(svc, "redis_lock", _lock(False)),
        ):
            with pytest.raises(ConflictError):
                await svc.sync_daily(session, _TRADE_DATE)
        session.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_gateway_error_propagates_without_commit(self) -> None:
        session = AsyncMock()
        client = MagicMock()
        client.get_intraday_orders = AsyncMock(
            side_effect=PaperTradeGatewayError("柜台错误")
        )

        with (
            patch.object(svc, "get_settings", lambda: _settings()),
            patch.object(svc, "redis_lock", _lock(True)),
            patch.object(svc, "PaperTradeClient", lambda url: client),
        ):
            with pytest.raises(PaperTradeGatewayError):
                await svc.sync_daily(session, _TRADE_DATE)
        session.commit.assert_not_awaited()
