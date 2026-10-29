"""历史持仓快照重放契约测试（成本加权/清仓/权重/跳过已写/缺收盘价口径）。"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.trading import position_replay
from app.services.trading.paper_trade_converters import SIDE_BUY, SIDE_SELL

_DAY1 = date(2026, 9, 21)
_DAY2 = date(2026, 9, 22)


def _execution(
    *,
    exec_id: int,
    day: date,
    symbol: str,
    side: int,
    price: str,
    volume: int,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=exec_id,
        trade_date=day,
        symbol=symbol,
        side=side,
        price=Decimal(price),
        volume=volume,
        counter_created_at=None,
    )


def _result(rows: list) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value = list(rows)
    result.all.return_value = list(rows)
    return result


@pytest.mark.unit
class TestApplyExecutions:
    def test_buy_weighted_avg_and_sell_keeps_cost(self) -> None:
        positions: dict[str, position_replay._Position] = {}
        position_replay._apply_executions(
            positions,
            {},
            [
                _execution(
                    exec_id=1, day=_DAY1, symbol="SHSE.600000", side=SIDE_BUY,
                    price="10", volume=100,
                ),
                _execution(
                    exec_id=2, day=_DAY1, symbol="SHSE.600000", side=SIDE_BUY,
                    price="20", volume=100,
                ),
            ],
        )
        position = positions["600000"]
        assert position.volume == 200
        assert position.avg_price == Decimal("15")

        position_replay._apply_executions(
            positions,
            {},
            [
                _execution(
                    exec_id=3, day=_DAY2, symbol="SHSE.600000", side=SIDE_SELL,
                    price="30", volume=50,
                )
            ],
        )
        assert position.volume == 150
        # 卖出按原成本冲减：成本总额 3000 - 15×50 = 2250，均价仍 15
        assert position.cost == Decimal("2250")
        assert position.avg_price == Decimal("15")

    def test_sell_to_zero_drops_position(self) -> None:
        positions: dict[str, position_replay._Position] = {}
        position_replay._apply_executions(
            positions,
            {},
            [
                _execution(
                    exec_id=1, day=_DAY1, symbol="SZSE.000001", side=SIDE_BUY,
                    price="10", volume=100,
                ),
                _execution(
                    exec_id=2, day=_DAY2, symbol="SZSE.000001", side=SIDE_SELL,
                    price="11", volume=100,
                ),
            ],
        )
        assert positions == {}

    def test_tracks_bought_today_for_t_plus_one(self) -> None:
        positions: dict[str, position_replay._Position] = {}
        bought: dict[str, int] = {}
        position_replay._apply_executions(
            positions,
            bought,
            [
                _execution(
                    exec_id=1, day=_DAY1, symbol="SHSE.600000", side=SIDE_BUY,
                    price="10", volume=300,
                )
            ],
        )
        assert bought == {"600000": 300}


@pytest.mark.unit
class TestSnapshotRows:
    def test_values_weight_and_available(self) -> None:
        positions = {
            "600000": position_replay._Position(),
            "000001": position_replay._Position(),
        }
        positions["600000"].volume, positions["600000"].cost = 1000, Decimal("10000")
        positions["000001"].volume, positions["000001"].cost = 500, Decimal("10000")
        rows = position_replay._snapshot_rows(
            positions,
            {"600000": 1000},
            _DAY1,
            {"600000": Decimal("11"), "000001": Decimal("20")},
            {},
        )
        by_code = {row["stock_code"]: row for row in rows}
        first = by_code["600000"]
        assert first["trade_date"] == _DAY1
        assert first["available_volume"] == 0  # 当日买入 T+1 不可卖
        assert first["avg_price"] == Decimal("10.0000")
        assert first["market_value"] == Decimal("11000.00")
        assert first["profit"] == Decimal("1000.00")
        assert first["profit_rate"] == Decimal("10.0000")
        # 市值 11000 + 10000 = 21000 → 权重 52.3810 / 47.6190
        assert first["weight"] == Decimal("52.3810")
        assert by_code["000001"]["weight"] == Decimal("47.6190")
        assert by_code["000001"]["available_volume"] == 500

    def test_missing_close_carries_last_known(self) -> None:
        positions = {"600000": position_replay._Position()}
        positions["600000"].volume, positions["600000"].cost = 100, Decimal("1000")
        last_close = {"600000": Decimal("12")}
        rows = position_replay._snapshot_rows(positions, {}, _DAY1, {}, last_close)
        assert rows[0]["last_price"] == Decimal("12")
        assert rows[0]["market_value"] == Decimal("1200.00")

    def test_never_priced_falls_back_to_cost(self) -> None:
        positions = {"600000": position_replay._Position()}
        positions["600000"].volume, positions["600000"].cost = 100, Decimal("1000")
        rows = position_replay._snapshot_rows(positions, {}, _DAY1, {}, {})
        assert rows[0]["last_price"] == Decimal("10.0000")
        assert rows[0]["market_value"] == Decimal("1000.00")


@pytest.mark.unit
class TestRebuildPositionSnapshots:
    @pytest.mark.asyncio
    async def test_replays_days_and_skips_existing(self) -> None:
        session = AsyncMock()
        executions = [
            _execution(
                exec_id=1, day=_DAY1, symbol="SHSE.600000", side=SIDE_BUY,
                price="10", volume=100,
            )
        ]
        session.execute = AsyncMock(
            side_effect=[
                _result([_DAY1, _DAY2]),  # 交易日历
                _result(executions),  # 成交回报
                _result([("600000", _DAY1, Decimal("11"))]),  # 收盘价
                _result([_DAY2]),  # 已有快照日
                MagicMock(),  # 插入
            ]
        )

        summary = await position_replay.rebuild_position_snapshots(
            session, account_id=7, start_date=_DAY1, end_date=_DAY2
        )

        assert summary["trading_days"] == 2
        assert summary["written_days"] == 1
        assert summary["skipped_days"] == 1
        assert summary["rows_written"] == 1
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_overwrite_deletes_range_before_insert(self) -> None:
        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[
                _result([_DAY1]),
                _result(
                    [
                        _execution(
                            exec_id=1, day=_DAY1, symbol="SHSE.600000",
                            side=SIDE_BUY, price="10", volume=100,
                        )
                    ]
                ),
                _result([]),  # 无收盘价
                MagicMock(),  # delete
                MagicMock(),  # insert
            ]
        )

        summary = await position_replay.rebuild_position_snapshots(
            session, account_id=7, start_date=_DAY1, end_date=_DAY1, overwrite=True
        )

        assert summary["rows_written"] == 1
        assert session.execute.await_count == 5

    @pytest.mark.asyncio
    async def test_no_executions_returns_reason(self) -> None:
        session = AsyncMock()
        empty = MagicMock()
        empty.scalar.return_value = None
        session.execute = AsyncMock(return_value=empty)

        summary = await position_replay.rebuild_position_snapshots(
            session, account_id=7, end_date=_DAY2
        )

        assert summary["reason"] == "no-executions"
        assert summary["rows_written"] == 0
        session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejects_reversed_range(self) -> None:
        session = AsyncMock()
        with pytest.raises(ValueError, match="晚于"):
            await position_replay.rebuild_position_snapshots(
                session, account_id=7, start_date=_DAY2, end_date=_DAY1
            )
