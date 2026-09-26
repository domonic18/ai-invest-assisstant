"""交易 Agent 下单风控硬校验（对话与定时执行共用的确定性代码，D18）。

规则集（docs/plan/paper-trading-plan.md §11.3，参数读 ``trading_agent_config``）：
禁 ST 买入、单票市值上限、总持仓上限、单日委托笔数、T+1、整手与科创板最低
200 股、限价单涨跌停区间。判定逻辑为纯函数 ``evaluate_order_risk``（表驱动
单测钉死全分支）；``check_order_risk`` 负责汇聚行情/柜台/本地表输入。

全部 fail-closed：行情、昨收、总资产等关键输入缺失视为不通过，原因列表供
LLM 转述或批次 8 计划保持 active 记录（不告警式失败）。
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import today_cn
from app.models.paper_trade import PaperTradeAccount, PaperTradeOrder
from app.services.trading import account_service
from app.services.trading.client import get_client
from app.services.trading.paper_trade_converters import unwrap_rows
from app.services.trading.paper_trade_mappers import normalize_cash_row

logger = structlog.get_logger(__name__)

SIDE_BUY = 1
SIDE_SELL = 2

#: 科创板最低申报 200 股、1 股递增（创业板仍 100 股整手）
STAR_MIN_VOLUME = 200
LOT_SIZE = 100


@dataclass(slots=True)
class RiskConfig:
    """风控阈值（来源 trading_agent_config，批次 8 定时执行同源消费）。"""

    max_position_pct: float
    max_total_pct: float
    max_daily_orders: int


@dataclass(slots=True)
class RiskOrderInput:
    """单笔委托的风控判定输入（async 汇聚层组装，纯函数只读）。"""

    stock_code: str
    stock_name: str | None
    side: int
    volume: int
    price: float
    order_type: str
    prev_close: float | None
    nav: float | None
    position_value: float
    position_volume: int
    total_position_value: float
    daily_order_count: int
    bought_today: int = 0


@dataclass(slots=True)
class RiskCheckResult:
    """判定结果：passed=False 时 reasons 供转述/记录（全量列出，不只首条）。"""

    passed: bool
    reasons: list[str] = field(default_factory=list)


def price_limit_pct(stock_name: str | None, stock_code: str) -> float:
    """涨跌停幅度（%）：ST ±5，创业板(30)/科创板(68) ±20，其余 ±10（服务端复刻前端规则）。"""
    if stock_name and "ST" in stock_name.upper():
        return 5.0
    if stock_code.startswith("30") or stock_code.startswith("68"):
        return 20.0
    return 10.0


def limit_prices(prev_close: float, limit_pct: float) -> tuple[float, float]:
    """按昨收推算（跌停价, 涨停价），四舍五入到分。"""
    factor = limit_pct / 100
    limit_up = round(prev_close * (1 + factor) * 100) / 100
    limit_down = round(prev_close * (1 - factor) * 100) / 100
    return limit_down, limit_up


def evaluate_order_risk(order: RiskOrderInput, config: RiskConfig) -> RiskCheckResult:
    """纯函数风控判定（无 IO，全规则独立累计，fail-closed）。"""
    reasons: list[str] = []
    is_buy = order.side == SIDE_BUY

    if order.volume <= 0:
        reasons.append("下单数量必须为正数")

    # 禁 ST 买入（卖出不止损通道不封）
    if is_buy and order.stock_name and "ST" in order.stock_name.upper():
        reasons.append(f"{order.stock_code}（{order.stock_name}）为 ST/退市风险股，禁止买入")

    # 整手与科创板最低申报
    if is_buy:
        if order.stock_code.startswith("68"):
            if order.volume < STAR_MIN_VOLUME:
                reasons.append(f"科创板最低申报 {STAR_MIN_VOLUME} 股（当前 {order.volume} 股）")
        elif order.volume % LOT_SIZE != 0:
            reasons.append(f"买入数量须为 {LOT_SIZE} 股整数倍（当前 {order.volume} 股）")

    # 涨跌停区间（限价单；市价单由柜台处理）
    order_value = order.price * order.volume
    if order.order_type == "limit":
        if order.price <= 0:
            reasons.append("限价单必须提供有效价格")
        elif order.prev_close is None:
            reasons.append("无法获取昨收价，无法校验涨跌停区间（fail-closed 拒单）")
        else:
            limit_down, limit_up = limit_prices(
                order.prev_close, price_limit_pct(order.stock_name, order.stock_code)
            )
            if not (limit_down <= order.price <= limit_up):
                reasons.append(
                    f"限价 {order.price} 超出涨跌停区间 [{limit_down}, {limit_up}]"
                    f"（昨收 {order.prev_close}）"
                )
    elif is_buy and order.price <= 0:
        # 市价买单以昨收估算占用资金
        if order.prev_close is None:
            reasons.append("无法获取昨收价，无法估算市价单占用资金（fail-closed 拒单）")
        else:
            order_value = order.prev_close * order.volume

    # 仓位上限（仅买入方向）
    if is_buy and order_value > 0:
        if order.nav is None:
            reasons.append("无法获取账户总资产，无法校验仓位上限（fail-closed 拒单）")
        else:
            position_cap = order.nav * config.max_position_pct / 100
            if order.position_value + order_value > position_cap:
                reasons.append(
                    f"单票市值超上限：买入后约 {order.position_value + order_value:.2f}"
                    f" > 总资产 {order.nav:.2f} × {config.max_position_pct:g}%（{position_cap:.2f}）"
                )
            total_cap = order.nav * config.max_total_pct / 100
            if order.total_position_value + order_value > total_cap:
                reasons.append(
                    f"总持仓超上限：买入后约 {order.total_position_value + order_value:.2f}"
                    f" > 总资产 {order.nav:.2f} × {config.max_total_pct:g}%（{total_cap:.2f}）"
                )

    # T+1：当日买入的股票不可当日卖出
    if not is_buy and order.bought_today > 0:
        sellable = order.position_volume - order.bought_today
        if order.volume > sellable:
            reasons.append(
                f"T+1 限制：{order.stock_code} 当日已买入 {order.bought_today} 股，"
                f"当前最多可卖 {max(sellable, 0)} 股（持仓 {order.position_volume} 股）"
            )

    # 单日委托笔数
    if order.daily_order_count >= config.max_daily_orders:
        reasons.append(
            f"当日委托笔数已达上限 {config.max_daily_orders}（已 {order.daily_order_count} 笔）"
        )

    return RiskCheckResult(passed=not reasons, reasons=reasons)


async def check_order_risk(
    session: AsyncSession,
    account: PaperTradeAccount,
    config: RiskConfig,
    *,
    stock_code: str,
    side: int,
    volume: int,
    price: float,
    order_type: str,
) -> RiskCheckResult:
    """汇聚行情 / 柜台实时 / 本地表输入后执行风控判定。

    Raises:
        PaperTradeNotConfiguredError: paper_trade_url 未配置。
        PaperTradeGatewayError: sidecar 或柜台错误。
    """
    from app.services.market import stock_service
    from app.services.trading.paper_trade_service import _bought_today_by_code

    today: date = today_cn()

    quote: dict[str, Any] | None = await stock_service.get_stock_quote(session, stock_code)
    stock_name = str(quote["name"]) if quote and quote.get("name") else None
    prev_close = float(quote["prev_close"]) if quote and quote.get("prev_close") else None

    client = get_client()
    credentials = account_service.credentials_for(account)
    cash = normalize_cash_row(await client.get_cash(credentials), today)
    nav = float(cash["nav"]) if cash.get("nav") is not None else None

    position_value = 0.0
    total_position_value = 0.0
    position_volume = 0
    for row in unwrap_rows(await client.get_positions(credentials)):
        market_value = row.get("market_value")
        value = float(market_value) if market_value is not None else 0.0
        total_position_value += value
        if str(row.get("stock_code") or "") == stock_code:
            position_value = value
            row_volume = row.get("volume")
            position_volume = int(row_volume) if row_volume is not None else 0

    daily_order_count = int(
        await session.scalar(
            select(func.count())
            .select_from(PaperTradeOrder)
            .where(
                PaperTradeOrder.paper_trade_account_id == account.id,
                PaperTradeOrder.trade_date == today,
                PaperTradeOrder.status != 8,  # 已拒委托未进市场，不计笔数
            )
        )
        or 0
    )

    bought_today = (await _bought_today_by_code(session, account.id, today)).get(
        stock_code, 0
    )

    result = evaluate_order_risk(
        RiskOrderInput(
            stock_code=stock_code,
            stock_name=stock_name,
            side=side,
            volume=volume,
            price=price,
            order_type=order_type,
            prev_close=prev_close,
            nav=nav,
            position_value=position_value,
            position_volume=position_volume,
            total_position_value=total_position_value,
            daily_order_count=daily_order_count,
            bought_today=bought_today,
        ),
        config,
    )
    if not result.passed:
        logger.info(
            "trading_agent_risk_rejected",
            account_id=account.id,
            stock_code=stock_code,
            side=side,
            volume=volume,
            reasons=result.reasons,
        )
    return result


def risk_config_from_row(
    *, max_position_pct: Decimal | float, max_total_pct: Decimal | float, max_daily_orders: int
) -> RiskConfig:
    """ORM 配置行 → 风控参数（Numeric → float 边界收敛）。"""
    return RiskConfig(
        max_position_pct=float(max_position_pct),
        max_total_pct=float(max_total_pct),
        max_daily_orders=int(max_daily_orders),
    )
