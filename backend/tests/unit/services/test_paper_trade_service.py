"""模拟盘盘后同步服务测试（规范化 / 幂等 upsert / 多账户错误隔离 / 锁与未配置语义）。"""

from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError
from app.services.trading import client as client_mod
from app.services.trading import paper_trade_converters as cvt
from app.services.trading import paper_trade_mappers as mappers
from app.services.trading import paper_trade_service as svc
from app.services.trading import paper_trade_sync as sync_svc
from app.services.trading.client import CounterCredentials
from app.services.trading.errors import (
    PaperTradeGatewayError,
    PaperTradeNotConfiguredError,
)

_TRADE_DATE = date(2026, 9, 24)
_CRED = CounterCredentials(token="tok", account_id="acc")


def _lock(acquired: bool = True):
    @asynccontextmanager
    async def _fake(key: str, ttl: int = 300):
        yield acquired

    return _fake


def _account(
    account_id: int = 1, agent_key: str | None = None, is_enabled: bool = True
) -> SimpleNamespace:
    return SimpleNamespace(
        id=account_id,
        name=f"账户{account_id}",
        agent_key=agent_key,
        is_enabled=is_enabled,
    )


def _accounts_result(accounts: list) -> MagicMock:
    # sync_daily 的账户清单是列 Row 查询（.all() 直取，无 scalars）
    res = MagicMock()
    res.all.return_value = accounts
    return res


@pytest.mark.unit
class TestNormalizeHelpers:
    def test_stock_code_strips_prefix(self) -> None:
        assert cvt.bare_stock_code("SHSE.600000") == "600000"
        assert cvt.bare_stock_code("600000") == "600000"

    def test_counter_datetime_epoch_seconds_and_ms(self) -> None:
        expected = datetime(2026, 9, 24, 8, 0, tzinfo=timezone.utc)
        assert cvt.parse_counter_datetime(1_790_236_800) == expected
        assert cvt.parse_counter_datetime(1_790_236_800_000) == expected

    def test_counter_datetime_iso_variants(self) -> None:
        assert cvt.parse_counter_datetime("2026-09-24T16:05:00+08:00") == datetime(
            2026, 9, 24, 8, 5, tzinfo=timezone.utc
        )
        # naive ISO 视作 UTC（兜底，不抛错）
        assert cvt.parse_counter_datetime("2026-09-24T08:00:00") == datetime(
            2026, 9, 24, 8, 0, tzinfo=timezone.utc
        )
        assert cvt.parse_counter_datetime("not-a-date") is None
        assert cvt.parse_counter_datetime("") is None
        assert cvt.parse_counter_datetime(None) is None

    def test_cn_trade_date_crosses_midnight(self) -> None:
        # UTC 24 日 16:05 = CN 25 日 00:05，业务日归 25 日
        dt = datetime(2026, 9, 24, 16, 5, tzinfo=timezone.utc)
        assert cvt.counter_cn_trade_date(dt, _TRADE_DATE) == date(2026, 9, 25)
        assert cvt.counter_cn_trade_date(None, _TRADE_DATE) == _TRADE_DATE

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
        rows = mappers.normalize_order_rows(
            raw, _TRADE_DATE, account_id=7, order_source="agent"
        )

        assert len(rows) == 1
        row = rows[0]
        assert row["paper_trade_account_id"] == 7
        assert row["order_source"] == "agent"
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
        rows = mappers.normalize_execution_rows(raw, _TRADE_DATE, account_id=7)

        assert len(rows) == 2
        assert rows[0]["paper_trade_account_id"] == 7
        assert rows[0]["exec_id"] == "e1"
        assert rows[1]["exec_id"] == f"o2:{datetime(2026, 9, 24, 3, 0, tzinfo=timezone.utc).isoformat()}"
        assert rows[1]["trade_date"] == _TRADE_DATE

    def test_normalize_executions_turnover_fallback(self) -> None:
        """掘金回报不带 turnover：按 价×量 本地补算，柜台给值时透传。"""
        raw = [
            {
                "ex_exec_id": "e1",
                "cl_ord_id": "o1",
                "symbol": "SZSE.002520",
                "side": 1,
                "price": 6.47,
                "volume": 4000,
            },
            {
                "ex_exec_id": "e2",
                "cl_ord_id": "o2",
                "symbol": "SZSE.002520",
                "price": 6.47,
                "volume": 4000,
                "turnover": 25881.0,
            },
        ]
        rows = mappers.normalize_execution_rows(raw, _TRADE_DATE, account_id=7)

        assert rows[0]["turnover"] == Decimal("25880.00")  # 6.47*4000
        assert rows[1]["turnover"] == Decimal("25881.0")

    def test_normalize_cash_ignores_non_dict(self) -> None:
        row = mappers.normalize_cash_row([], _TRADE_DATE)
        assert row["trade_date"] == _TRADE_DATE
        assert row["nav"] is None

        row = mappers.normalize_cash_row({"nav": "123456.78", "available": 1000}, _TRADE_DATE)
        assert row["nav"] == Decimal("123456.78")
        assert row["available"] == Decimal("1000")

    def test_normalize_cash_unwraps_counter_list(self) -> None:
        # 实测柜台对单个 cash 对象也包数组返回
        row = mappers.normalize_cash_row(
            [{"nav": 200000, "available": 200000, "balance": 200000}], _TRADE_DATE
        )
        assert row["nav"] == Decimal("200000")
        assert row["trade_date"] == _TRADE_DATE


def _settings(url: str = "http://paper-trade:8020") -> SimpleNamespace:
    return SimpleNamespace(paper_trade_url=url, paper_trade_timeout=1.0)


@pytest.mark.unit
class TestWireMappers:
    def test_order_wire_row_maps_counter_payload(self) -> None:
        row = mappers.order_wire_row(
            {
                "cl_ord_id": "u1",
                "symbol": "SHSE.600000",
                "side": 1,
                "order_type": 1,
                "price": "8.5",
                "volume": 100,
                "status": 1,
                "created_at": "2026-09-24T01:15:00Z",
            },
            _TRADE_DATE,
        )
        assert row["cl_ord_id"] == "u1"
        assert row["stock_code"] == "600000"
        assert row["price"] == Decimal("8.5")
        assert row["trade_date"] == _TRADE_DATE

    def test_position_wire_row_candidate_keys(self) -> None:
        row = mappers.position_wire_row(
            {
                "symbol": "SZSE.000001",
                "side": 1,
                "volume": 100,
                "vwap": "12.34",
                "last_price": 12.5,
                "float_profit": "-16",
            }
        )
        assert row["stock_code"] == "000001"
        assert row["avg_price"] == Decimal("12.34")
        assert row["last_price"] == Decimal("12.5")
        assert row["profit"] == Decimal("-16")
        assert row["available_volume"] is None
        # 柜台给 profit 缺 profit_rate 时本地补算：-16/(12.34*100)*100
        assert row["profit_rate"] == Decimal("-1.2966")


@pytest.mark.unit
class TestGetOverview:
    @pytest.mark.asyncio
    async def test_raises_when_not_configured(self) -> None:
        with patch.object(client_mod, "get_settings", lambda: _settings(url="")):
            with pytest.raises(PaperTradeNotConfiguredError):
                await svc.get_overview(MagicMock(), _account())

    @pytest.mark.asyncio
    async def test_transparent_passthrough_normalization(self) -> None:
        client = MagicMock()
        client.get_cash = AsyncMock(
            return_value=[{"nav": 200000, "available": 198000, "balance": 200000}]
        )
        client.get_positions = AsyncMock(return_value={})  # 空结果 {}
        client.get_unfinished_orders = AsyncMock(
            return_value=[
                {
                    "cl_ord_id": "u1",
                    "symbol": "SZSE.000001",
                    "side": 2,
                    "order_type": 1,
                    "price": 12.0,
                    "volume": 200,
                    "status": 1,
                    "created_at": "2026-09-24T01:15:00Z",
                }
            ]
        )
        session = MagicMock()
        session.execute = AsyncMock(return_value=MagicMock(all=lambda: []))

        with (
            patch.object(client_mod, "get_settings", lambda: _settings()),
            patch.object(client_mod, "PaperTradeClient", lambda url: client),
            patch.object(
                svc.account_service, "credentials_for", lambda account: _CRED
            ),
        ):
            payload = await svc.get_overview(session, _account(account_id=7))

        assert payload["enabled"] is True
        assert payload["cash"] == {
            "nav": 200000.0,
            "available": 198000.0,
            "balance": 200000.0,
            "cum_inout": None,
            "last_inout": None,
        }
        assert payload["positions"] == []
        row = payload["unfinished_orders"][0]
        assert row["cl_ord_id"] == "u1"
        assert row["trade_date"] == _TRADE_DATE
        assert row["side"] == 2
        client.get_cash.assert_awaited_once_with(_CRED)

    @pytest.mark.asyncio
    async def test_t1_available_deducts_today_buys(self) -> None:
        """掘金 available 含当日买入（T+1 不符），overview 须扣减本地今日成交买入。"""
        client = MagicMock()
        client.get_cash = AsyncMock(return_value={})
        client.get_positions = AsyncMock(
            return_value=[
                {
                    "symbol": "SZSE.002520",
                    "volume": 4000,
                    "available_volume": 4000,
                    "price": 6.45,
                    "last_price": 6.47,
                    "market_value": 25800.0,
                },
                {
                    # 昨日持仓无今日买入：可用数保持柜台原值
                    "symbol": "SHSE.600000",
                    "volume": 500,
                    "available_volume": 500,
                    "price": 10.0,
                    "last_price": 10.5,
                },
            ]
        )
        client.get_unfinished_orders = AsyncMock(return_value={})
        session = MagicMock()
        session.execute = AsyncMock(
            return_value=MagicMock(
                all=lambda: [("SZSE.002520", 4000), ("SHSE.688322", 0)]
            )
        )

        with (
            patch.object(client_mod, "get_settings", lambda: _settings()),
            patch.object(client_mod, "PaperTradeClient", lambda url: client),
            patch.object(
                svc.account_service, "credentials_for", lambda account: _CRED
            ),
        ):
            payload = await svc.get_overview(session, _account(account_id=7))

        by_code = {p["stock_code"]: p for p in payload["positions"]}
        assert by_code["002520"]["available_volume"] == 0
        assert by_code["600000"]["available_volume"] == 500

    @pytest.mark.asyncio
    async def test_position_profit_fallback_and_quantize(self) -> None:
        """柜台缺浮盈本地补算；float32 尾噪声 quantize 收敛。"""
        client = MagicMock()
        client.get_cash = AsyncMock(return_value={})
        client.get_positions = AsyncMock(
            return_value=[
                {
                    "symbol": "SZSE.002520",
                    "volume": 4000,
                    "available_volume": 4000,
                    "price": 6.449999809265137,
                    "last_price": 6.46999979019165,
                    "market_value": 25799.999237060547,
                }
            ]
        )
        client.get_unfinished_orders = AsyncMock(return_value={})
        session = MagicMock()
        session.execute = AsyncMock(return_value=MagicMock(all=lambda: []))

        with (
            patch.object(client_mod, "get_settings", lambda: _settings()),
            patch.object(client_mod, "PaperTradeClient", lambda url: client),
            patch.object(
                svc.account_service, "credentials_for", lambda account: _CRED
            ),
        ):
            payload = await svc.get_overview(session, _account(account_id=7))

        row = payload["positions"][0]
        assert row["avg_price"] == Decimal("6.4500")
        assert row["last_price"] == Decimal("6.4700")
        assert row["market_value"] == Decimal("25800.00")
        assert row["profit"] == Decimal("80.00")  # (6.47-6.45)*4000
        assert row["profit_rate"] == Decimal("0.3101")  # 80 / (6.45*4000) * 100


@pytest.mark.unit
class TestManualTrading:
    @pytest.mark.asyncio
    async def test_place_order_rejects_agent_account(self) -> None:
        with pytest.raises(ForbiddenError):
            await svc.place_order(
                MagicMock(),
                _account(agent_key="short-line"),
                symbol="000001",
                side="buy",
                volume=100,
            )

    @pytest.mark.asyncio
    async def test_place_order_forwards_with_credentials(self) -> None:
        client = MagicMock()
        client.place_order = AsyncMock(return_value=[{"cl_ord_id": "n1"}])

        with (
            patch.object(client_mod, "get_settings", lambda: _settings()),
            patch.object(client_mod, "PaperTradeClient", lambda url: client),
            patch.object(
                svc.account_service, "credentials_for", lambda account: _CRED
            ),
            patch.object(
                svc, "resolve_counter_symbol", AsyncMock(return_value="SHSE.600000")
            ),
        ):
            payload = await svc.place_order(
                MagicMock(),
                _account(),
                symbol="600000",
                side="buy",
                volume=100,
                price=8.5,
            )

        assert payload == [{"cl_ord_id": "n1"}]
        args, kwargs = client.place_order.await_args
        assert args[0] == _CRED
        assert args[1] == "SHSE.600000"
        assert args[3] == 100
        assert kwargs["price"] == 8.5

    @pytest.mark.asyncio
    async def test_cancel_order_rejects_agent_account(self) -> None:
        with pytest.raises(ForbiddenError):
            await svc.cancel_order(_account(agent_key="short-line"), "o1")

    @pytest.mark.asyncio
    async def test_place_order_rejects_disabled_account(self) -> None:
        """停用账户禁止人工交易（与前端禁用态同契约，仅同步跳过不够）。"""
        with pytest.raises(ForbiddenError, match="停用"):
            await svc.place_order(
                MagicMock(),
                _account(is_enabled=False),
                symbol="000001",
                side="buy",
                volume=100,
            )

    @pytest.mark.asyncio
    async def test_cancel_order_forwards_with_credentials(self) -> None:
        client = MagicMock()
        client.cancel_order = AsyncMock(return_value={})

        with (
            patch.object(client_mod, "get_settings", lambda: _settings()),
            patch.object(client_mod, "PaperTradeClient", lambda url: client),
            patch.object(
                svc.account_service, "credentials_for", lambda account: _CRED
            ),
        ):
            await svc.cancel_order(_account(), "o1")

        client.cancel_order.assert_awaited_once_with(_CRED, "o1")


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
        with patch.object(client_mod, "get_settings", lambda: _settings(url="")):
            with pytest.raises(PaperTradeNotConfiguredError):
                await svc.sync_daily(session, _TRADE_DATE)
        session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_raises_when_no_enabled_accounts(self) -> None:
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_accounts_result([]))

        with patch.object(client_mod, "get_settings", lambda: _settings()):
            with pytest.raises(PaperTradeNotConfiguredError, match="启用"):
                await svc.sync_daily(session, _TRADE_DATE)
        session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_accounts_query_selects_columns_not_entities(self) -> None:
        """账户清单必须是列 Row 查询：per-account rollback 会过期 ORM identity map，
        实体查询会让后续账户的属性访问在 greenlet 外触发隐式 lazy load（生产事故回归）。"""
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_accounts_result([]))
        with patch.object(client_mod, "get_settings", lambda: _settings()):
            with pytest.raises(PaperTradeNotConfiguredError):
                await svc.sync_daily(session, _TRADE_DATE)
        stmt = session.execute.call_args[0][0]
        assert set(stmt.selected_columns.keys()) == {
            "id",
            "name",
            "agent_key",
            "counter_account_id",
            "token_encrypted",
        }

    @pytest.mark.asyncio
    async def test_happy_path_upserts_three_tables(self) -> None:
        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[
                _accounts_result([_account(account_id=7)]),
                MagicMock(),  # 委托 upsert
                MagicMock(),  # 回报插入
                MagicMock(),  # 资金快照 upsert
                MagicMock(),  # 账户同步状态 update
            ]
        )
        orders = [{"cl_ord_id": "o1", "symbol": "SHSE.600000", "status": 3}]
        executions = [{"ex_exec_id": "e1", "cl_ord_id": "o1"}]
        cash = {"nav": "100000.00"}

        with (
            patch.object(client_mod, "get_settings", lambda: _settings()),
            patch.object(sync_svc, "redis_lock", _lock(True)),
            patch.object(
                client_mod, "PaperTradeClient", lambda url: _client_mock(orders, executions, cash)
            ),
            patch.object(
                svc.account_service, "credentials_for", lambda account: _CRED
            ),
        ):
            summary = await svc.sync_daily(session, _TRADE_DATE)

        assert summary["trade_date"] == _TRADE_DATE.isoformat()
        assert summary["accounts"] == 1
        assert summary["orders"] == 1
        assert summary["executions"] == 1
        assert summary["failed"] == 0
        assert summary["details"][0]["nav"] == 100000.0
        assert summary["details"][0]["error"] is None
        # 账户查询 + 委托 upsert + 回报插入 + 资金快照 upsert + 账户状态 update = 5 次
        assert session.execute.await_count == 5
        session.commit.assert_awaited_once()
        session.rollback.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_empty_counter_payloads_commit_snapshot_only(self) -> None:
        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[
                _accounts_result([_account()]),
                MagicMock(),  # 资金快照 upsert
                MagicMock(),  # 账户同步状态 update
            ]
        )

        with (
            patch.object(client_mod, "get_settings", lambda: _settings()),
            patch.object(sync_svc, "redis_lock", _lock(True)),
            patch.object(
                client_mod, "PaperTradeClient", lambda url: _client_mock([], [], {})
            ),
            patch.object(
                svc.account_service, "credentials_for", lambda account: _CRED
            ),
        ):
            summary = await svc.sync_daily(session, _TRADE_DATE)

        assert summary["orders"] == 0
        assert summary["executions"] == 0
        # 空委托/回报跳过写库，资金快照仍必须落（净值曲线连续性）
        assert session.execute.await_count == 3
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_agent_account_orders_tagged_agent_source(self) -> None:
        """agent 账户同步的委托行带 order_source=agent（落库值经 normalize_order_rows 钉死）。"""
        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[
                _accounts_result([_account(account_id=9, agent_key="short-line")]),
                MagicMock(),
                MagicMock(),
                MagicMock(),
                MagicMock(),
            ]
        )

        orders = [{"cl_ord_id": "a1", "symbol": "SHSE.600000", "status": 2}]

        with (
            patch.object(client_mod, "get_settings", lambda: _settings()),
            patch.object(sync_svc, "redis_lock", _lock(True)),
            patch.object(
                client_mod, "PaperTradeClient", lambda url: _client_mock(orders, [], {})
            ),
            patch.object(
                svc.account_service, "credentials_for", lambda account: _CRED
            ),
        ):
            summary = await svc.sync_daily(session, _TRADE_DATE)

        assert summary["orders"] == 1
        assert summary["details"][0]["agent_key"] == "short-line"
        assert summary["details"][0]["account_id"] == 9

    @pytest.mark.asyncio
    async def test_account_error_isolation(self) -> None:
        """第一个账户柜台报错不阻断第二个账户；失败写 last_error 并 commit。"""
        session = AsyncMock()
        accounts = [_account(account_id=1), _account(account_id=2, agent_key="short-line")]
        session.execute = AsyncMock(
            side_effect=[
                _accounts_result(accounts),
                MagicMock(),  # 账户1 失败态 update（last_error）
                MagicMock(),  # 账户2 委托
                MagicMock(),  # 账户2 回报
                MagicMock(),  # 账户2 快照
                MagicMock(),  # 账户2 同步状态 update
            ]
        )
        client = _client_mock([], [], {})
        client.get_intraday_orders = AsyncMock(
            side_effect=[PaperTradeGatewayError("柜台错误"), []]
        )

        with (
            patch.object(client_mod, "get_settings", lambda: _settings()),
            patch.object(sync_svc, "redis_lock", _lock(True)),
            patch.object(client_mod, "PaperTradeClient", lambda url: client),
            patch.object(
                svc.account_service, "credentials_for", lambda account: _CRED
            ),
        ):
            summary = await svc.sync_daily(session, _TRADE_DATE)

        assert summary["failed"] == 1
        assert summary["accounts"] == 2
        assert "柜台错误" in summary["details"][0]["error"]
        assert summary["details"][1]["error"] is None
        # 失败账户写 last_error commit + 成功账户 commit
        assert session.commit.await_count == 2
        # rollback 仅隔离失败账户的半程写入，不终止循环
        session.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_lock_not_acquired_raises_conflict(self) -> None:
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_accounts_result([_account()]))
        with (
            patch.object(client_mod, "get_settings", lambda: _settings()),
            patch.object(sync_svc, "redis_lock", _lock(False)),
        ):
            with pytest.raises(ConflictError):
                await svc.sync_daily(session, _TRADE_DATE)
        # 账户清单在锁外查询；锁被占时不发生任何写库
        session.execute.assert_awaited_once()
        session.commit.assert_not_awaited()


def _patch_trade_date() -> "patch":
    return patch(
        "app.services.market.trade_calendar_service.resolve_latest_trade_date",
        AsyncMock(return_value=_TRADE_DATE),
    )


@pytest.mark.unit
class TestSyncAccountNow:
    @pytest.mark.asyncio
    async def test_syncs_upserts_and_commits(self) -> None:
        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[
                MagicMock(),  # 委托 upsert
                MagicMock(),  # 资金快照 upsert（空回报跳过执行）
                MagicMock(),  # 账户同步状态 update
            ]
        )
        orders = [{"cl_ord_id": "o1", "symbol": "SHSE.600000", "status": 1}]

        with (
            patch.object(client_mod, "get_settings", lambda: _settings()),
            patch.object(sync_svc, "redis_lock", _lock(True)),
            patch.object(
                client_mod, "PaperTradeClient", lambda url: _client_mock(orders, [], {"nav": "9999.0"})
            ),
            patch.object(
                svc.account_service, "credentials_for", lambda account: _CRED
            ),
            _patch_trade_date(),
        ):
            summary = await svc.sync_account_now(session, _account(account_id=7))

        assert summary["trade_date"] == _TRADE_DATE.isoformat()
        assert summary["account_id"] == 7
        assert summary["orders"] == 1
        assert summary["nav"] == 9999.0
        assert session.execute.await_count == 3
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_lock_conflict_raises(self) -> None:
        session = AsyncMock()
        with (
            patch.object(client_mod, "get_settings", lambda: _settings()),
            patch.object(sync_svc, "redis_lock", _lock(False)),
            _patch_trade_date(),
        ):
            with pytest.raises(ConflictError):
                await svc.sync_account_now(session, _account())
        session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_counter_error_propagates(self) -> None:
        """即时同步错误向上传播给用户（与盘后批量的账户间隔离不同）。"""
        session = AsyncMock()
        client = _client_mock([], [], {})
        client.get_intraday_orders = AsyncMock(side_effect=PaperTradeGatewayError("柜台错误"))

        with (
            patch.object(client_mod, "get_settings", lambda: _settings()),
            patch.object(sync_svc, "redis_lock", _lock(True)),
            patch.object(client_mod, "PaperTradeClient", lambda url: client),
            patch.object(
                svc.account_service, "credentials_for", lambda account: _CRED
            ),
            _patch_trade_date(),
        ):
            with pytest.raises(PaperTradeGatewayError):
                await svc.sync_account_now(session, _account())
        session.commit.assert_not_awaited()


def _stock(market: str) -> SimpleNamespace:
    return SimpleNamespace(stock_code="000037", market=market)


def _patch_master(stock: SimpleNamespace | None):
    return patch(
        "app.services.market.stock_service.get_stock_by_code",
        AsyncMock(return_value=stock),
    )


@pytest.mark.unit
class TestResolveCounterSymbol:
    """柜台代码解析：归属以 stock_basic.market 主数据为准（柜台对错误前缀静默受理永不撮合）。"""

    @pytest.mark.asyncio
    async def test_bare_code_resolved_from_master(self) -> None:
        session = MagicMock()
        for market, expected in [("sz", "SZSE.000037"), ("sh", "SHSE.000037"), ("bj", "BJSE.000037")]:
            with _patch_master(_stock(market)):
                assert await svc.resolve_counter_symbol(session, "000037") == expected

    @pytest.mark.asyncio
    async def test_prefixed_consistent_passes(self) -> None:
        with _patch_master(_stock("sz")):
            assert (
                await svc.resolve_counter_symbol(MagicMock(), "SZSE.000037")
                == "SZSE.000037"
            )

    @pytest.mark.asyncio
    async def test_prefixed_mismatched_rejected(self) -> None:
        with _patch_master(_stock("sz")):
            with pytest.raises(BadRequestError, match="SZSE.000037"):
                await svc.resolve_counter_symbol(MagicMock(), "SHSE.000037")

    @pytest.mark.asyncio
    async def test_unknown_code_rejected(self) -> None:
        with _patch_master(None):
            with pytest.raises(BadRequestError, match="主数据"):
                await svc.resolve_counter_symbol(MagicMock(), "999999")

    @pytest.mark.asyncio
    async def test_garbage_rejected(self) -> None:
        with pytest.raises(BadRequestError, match="无法识别"):
            await svc.resolve_counter_symbol(MagicMock(), "abc")


def _marker_row(side: int = 1, price: Decimal | None = Decimal("10.00")) -> SimpleNamespace:
    return SimpleNamespace(
        trade_date=date(2026, 9, 21),
        counter_created_at=datetime(2026, 9, 21, 1, 30, tzinfo=timezone.utc),
        side=side,
        price=price,
        volume=100,
    )


class TestGetTradeMarkers:
    @pytest.mark.asyncio
    async def test_rejects_invalid_code_without_db(self) -> None:
        session = MagicMock()
        with pytest.raises(BadRequestError, match="6 位"):
            await svc.get_trade_markers(session, 3, "abc")
        session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_rows_from_session(self) -> None:
        rows = [_marker_row(side=1), _marker_row(side=2)]
        result = MagicMock()
        result.scalars.return_value.all.return_value = rows
        session = MagicMock()
        session.execute = AsyncMock(return_value=result)
        got = await svc.get_trade_markers(session, 3, "000037", 120)
        assert got == rows

    @pytest.mark.asyncio
    async def test_empty_result(self) -> None:
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        session = MagicMock()
        session.execute = AsyncMock(return_value=result)
        assert await svc.get_trade_markers(session, 3, "600000") == []
