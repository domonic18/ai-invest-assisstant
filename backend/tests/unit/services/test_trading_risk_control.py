"""交易 Agent 风控硬校验测试（evaluate_order_risk 纯函数表驱动全分支 + 口径函数）。"""

from dataclasses import replace
from decimal import Decimal

import pytest

from app.services.trading.risk_control import (
    LOT_SIZE,
    STAR_MIN_VOLUME,
    RiskConfig,
    RiskOrderInput,
    evaluate_order_risk,
    limit_prices,
    price_limit_pct,
    risk_config_from_row,
)

CONFIG = RiskConfig(max_position_pct=20.0, max_total_pct=80.0, max_daily_orders=10)


def _order(**overrides: object) -> RiskOrderInput:
    """合规买入基线：浦发银行 100 股 @10 元（昨收 10），总资产 10 万、无持仓。"""
    base: dict[str, object] = {
        "stock_code": "600000",
        "stock_name": "浦发银行",
        "side": 1,
        "volume": 100,
        "price": 10.0,
        "order_type": "limit",
        "prev_close": 10.0,
        "nav": 100_000.0,
        "position_value": 0.0,
        "position_volume": 0,
        "total_position_value": 0.0,
        "daily_order_count": 0,
        "bought_today": 0,
    }
    base.update(overrides)
    return RiskOrderInput(**base)  # type: ignore[arg-type]


def _sell(**overrides: object) -> RiskOrderInput:
    return _order(side=2, **overrides)


@pytest.mark.unit
class TestHappyPath:
    def test_plain_buy_passes(self) -> None:
        assert evaluate_order_risk(_order(), CONFIG).passed

    def test_plain_sell_passes(self) -> None:
        assert evaluate_order_risk(
            _sell(
                position_value=10_000.0,
                position_volume=1_000,
                total_position_value=10_000.0,
            ),
            CONFIG,
        ).passed

    def test_market_buy_passes(self) -> None:
        assert evaluate_order_risk(_order(order_type="market", price=0.0), CONFIG).passed


@pytest.mark.unit
class TestVolumeRules:
    def test_zero_volume_rejected(self) -> None:
        result = evaluate_order_risk(_order(volume=0), CONFIG)
        assert not result.passed
        assert any("正数" in r for r in result.reasons)

    def test_main_board_lot_multiple(self) -> None:
        result = evaluate_order_risk(_order(volume=150), CONFIG)
        assert any(f"{LOT_SIZE} 股整数倍" in r for r in result.reasons)

    def test_star_minimum_200(self) -> None:
        result = evaluate_order_risk(_order(stock_code="688001", volume=100), CONFIG)
        assert any(f"科创板最低申报 {STAR_MIN_VOLUME}" in r for r in result.reasons)

    def test_star_200_not_lot_multiple_passes(self) -> None:
        """科创板 1 股递增：200 股即可（非 100 整数倍不拦）。"""
        assert evaluate_order_risk(_order(stock_code="688001", volume=201), CONFIG).passed


@pytest.mark.unit
class TestStBan:
    def test_st_buy_rejected(self) -> None:
        result = evaluate_order_risk(_order(stock_code="600001", stock_name="ST 星源"), CONFIG)
        assert any("禁止买入" in r for r in result.reasons)

    def test_st_lowercase_name_rejected(self) -> None:
        result = evaluate_order_risk(_order(stock_code="600001", stock_name="*st 大集"), CONFIG)
        assert any("禁止买入" in r for r in result.reasons)

    def test_st_sell_allowed(self) -> None:
        """卖出是止损通道，不封 ST。"""
        assert evaluate_order_risk(
            _sell(stock_name="ST 星源", position_value=1_000.0, position_volume=100), CONFIG
        ).passed


@pytest.mark.unit
class TestLimitPriceBand:
    def test_limit_above_10pct_rejected(self) -> None:
        result = evaluate_order_risk(_order(price=11.01), CONFIG)
        assert any("涨跌停区间" in r for r in result.reasons)

    def test_limit_below_down_rejected(self) -> None:
        result = evaluate_order_risk(_order(price=8.99), CONFIG)
        assert any("涨跌停区间" in r for r in result.reasons)

    def test_limit_at_band_passes(self) -> None:
        assert evaluate_order_risk(_order(price=11.0), CONFIG).passed
        assert evaluate_order_risk(_order(price=9.0), CONFIG).passed

    def test_limit_without_prev_close_fails_closed(self) -> None:
        result = evaluate_order_risk(_order(prev_close=None), CONFIG)
        assert any("fail-closed" in r for r in result.reasons)

    def test_limit_zero_price_rejected(self) -> None:
        result = evaluate_order_risk(_order(price=0.0), CONFIG)
        assert any("有效价格" in r for r in result.reasons)

    def test_market_buy_without_prev_close_fails_closed(self) -> None:
        result = evaluate_order_risk(_order(order_type="market", price=0.0, prev_close=None), CONFIG)
        assert any("估算市价单占用资金" in r for r in result.reasons)


@pytest.mark.unit
class TestPositionCaps:
    def test_position_cap_violated(self) -> None:
        """买入 2100 股 @10 = 2.1 万 > 10 万 × 20%。"""
        result = evaluate_order_risk(_order(volume=2100), CONFIG)
        assert any("单票市值超上限" in r for r in result.reasons)

    def test_position_cap_boundary_passes(self) -> None:
        assert evaluate_order_risk(_order(volume=2000), CONFIG).passed

    def test_total_cap_violated(self) -> None:
        """已有 7.5 万持仓，再买 6 千 → 8.1 万 > 8 万（单票上限内）。"""
        result = evaluate_order_risk(
            _order(volume=600, total_position_value=75_000.0), CONFIG
        )
        assert any("总持仓超上限" in r for r in result.reasons)
        assert all("单票市值超上限" not in r for r in result.reasons)

    def test_missing_nav_fails_closed_on_buy(self) -> None:
        result = evaluate_order_risk(_order(nav=None), CONFIG)
        assert any("总资产" in r for r in result.reasons)

    def test_sell_ignores_position_caps(self) -> None:
        assert evaluate_order_risk(
            _sell(nav=None, position_value=1_000.0, position_volume=100), CONFIG
        ).passed


@pytest.mark.unit
class TestT1AndDailyCount:
    def test_t1_sell_blocked(self) -> None:
        """持仓 1000 当日买入 200 → 最多可卖 800。"""
        result = evaluate_order_risk(
            _sell(volume=900, position_volume=1_000, bought_today=200), CONFIG
        )
        assert any("T+1" in r for r in result.reasons)

    def test_t1_sell_within_sellable_passes(self) -> None:
        assert evaluate_order_risk(
            _sell(volume=800, position_volume=1_000, bought_today=200,
                  position_value=8_000.0, total_position_value=8_000.0), CONFIG
        ).passed

    def test_daily_count_at_cap_rejected(self) -> None:
        result = evaluate_order_risk(_order(daily_order_count=10), CONFIG)
        assert any("当日委托笔数已达上限" in r for r in result.reasons)

    def test_daily_count_below_cap_passes(self) -> None:
        assert evaluate_order_risk(_order(daily_order_count=9), CONFIG).passed

    def test_sell_also_counts_toward_daily_cap(self) -> None:
        result = evaluate_order_risk(
            _sell(daily_order_count=10, position_volume=1_000, position_value=1_000.0), CONFIG
        )
        assert any("当日委托笔数已达上限" in r for r in result.reasons)


@pytest.mark.unit
class TestReasonAccumulation:
    def test_all_violations_listed_not_first_only(self) -> None:
        """数量 0 + 笔数超限同时列出（累计不只首条）。"""
        result = evaluate_order_risk(_order(volume=0, daily_order_count=10), CONFIG)
        assert len(result.reasons) >= 2

    def test_replacement_semantics(self) -> None:
        """replace 只改声明字段，基线其余合规（表驱动卫生检查）。"""
        case = replace(_order(), volume=150)
        assert any("整数倍" in r for r in evaluate_order_risk(case, CONFIG).reasons)


@pytest.mark.unit
class TestCalibration:
    def test_price_limit_pct(self) -> None:
        assert price_limit_pct("ST 星源", "600001") == 5.0
        assert price_limit_pct("创业板股", "300750") == 20.0
        assert price_limit_pct("科创板股", "688001") == 20.0
        assert price_limit_pct("浦发银行", "600000") == 10.0

    def test_limit_prices_round_to_cents(self) -> None:
        assert limit_prices(10.0, 10.0) == (9.0, 11.0)
        # 9.87 ±5%：四舍五入到分（9.3765 → 9.38 / 10.3635 → 10.36）
        assert limit_prices(9.87, 5.0) == (9.38, 10.36)

    def test_risk_config_from_row_decimal(self) -> None:
        config = risk_config_from_row(
            max_position_pct=Decimal("20.00"),
            max_total_pct=Decimal("80.00"),
            max_daily_orders=10,
        )
        assert config == CONFIG
