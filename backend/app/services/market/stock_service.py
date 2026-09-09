"""个股基础信息与行情业务服务。"""

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_redis
from app.core.clock import today_cn
from app.models.stock import StockBasic
from app.repositories.market import sector_fund_flow_repository
from app.repositories.market.kline_repository import fetch_daily_bars, fetch_daily_bars_multi
from app.repositories.market.stock_concept_repository import StockConceptRepository
from app.repositories.market.stock_repository import StockRepository


def _to_float(value: Any) -> float | None:
    return float(value) if value is not None else None


def _to_int(value: Any) -> int | None:
    return int(value) if value is not None else None


async def search_stocks(
    session: AsyncSession, query: str, limit: int = 20
) -> list[StockBasic]:
    """根据股票代码或名称模糊搜索。"""
    return await StockRepository(session).search_by_keyword(query, limit)


async def get_stock_by_code(
    session: AsyncSession, stock_code: str, market: str | None = None
) -> StockBasic | None:
    """通过股票代码查询基础信息。"""
    return await StockRepository(session).get_by_code(stock_code, market)


async def get_stock_quote(session: AsyncSession, stock_code: str) -> dict[str, Any] | None:
    """获取个股实时行情快照。

    Redis 实时键缺失时回退长 TTL 收盘兜底键（``quote:eod:``），再缺失回退最新
    日 K；全部 miss 时返回空值快照（股票不存在才返回 None 交给路由 404）。
    """
    stock = await get_stock_by_code(session, stock_code)
    if stock is None:
        return None

    name = stock.stock_name or stock_code
    price: float | None = None
    prev_close: float | None = None
    open_: float | None = None
    high: float | None = None
    low: float | None = None
    volume: int | None = None
    amount: float | None = None
    updated_at: str | None = None

    live, eod = await get_redis().mget(
        f"quote:{stock_code}", f"quote:eod:{stock_code}"
    )
    raw = live or eod
    if raw:
        cached = json.loads(raw)
        price = _to_float(cached.get("price"))
        prev_close = _to_float(cached.get("prev_close"))
        open_ = _to_float(cached.get("open"))
        high = _to_float(cached.get("high"))
        low = _to_float(cached.get("low"))
        volume = _to_int(cached.get("volume"))
        amount = _to_float(cached.get("amount"))
        updated_at = cached.get("updated_at")

    if price is None:
        # 快照未命中（盘后/周末），回退到最近两根日 K；
        # 日 K 也无行时保持空值返回（页面渲染占位），不再 404
        daily = [
            bar
            for bar in await fetch_daily_bars(session, stock_code, limit=2)
            if bar.close is not None
        ]
        if daily:
            latest = daily[0]
            prev = daily[1] if len(daily) > 1 else None
            price = _to_float(latest.close)
            prev_close = _to_float(prev.close) if prev else price
            open_ = _to_float(latest.open)
            high = _to_float(latest.high)
            low = _to_float(latest.low)
            volume = _to_int(latest.volume)
            amount = _to_float(latest.amount)
            updated_at = latest.trade_date.isoformat()

    change = (price - prev_close) if price is not None and prev_close is not None else None
    change_pct = (change / prev_close * 100) if change is not None and prev_close else None
    market_cap = (
        price * stock.total_shares
        if price is not None and stock.total_shares is not None
        else None
    )
    circulating_market_cap = (
        price * stock.circulating_shares
        if price is not None and stock.circulating_shares is not None
        else None
    )

    return {
        "code": stock_code,
        "name": name,
        "price": price,
        "prev_close": prev_close,
        "change": round(change, 4) if change is not None else None,
        "change_pct": round(change_pct, 4) if change_pct is not None else None,
        "open": open_,
        "high": high,
        "low": low,
        "volume": volume,
        "amount": amount,
        "market_cap": market_cap,
        "circulating_market_cap": circulating_market_cap,
        "updated_at": updated_at,
    }


async def batch_quote_snapshot(
    session: AsyncSession, codes: list[str]
) -> dict[str, dict[str, Any]]:
    """批量股票轻量快照：名称 + 当日涨跌幅（电报流等列表标注用）。

    涨跌幅口径与 ``get_stock_quote`` 一致：实时键 → 收盘兜底键 →
    最近两根日 K 推算；全部 miss 时 change_pct 为 None。
    """
    unique = list(dict.fromkeys(codes))
    if not unique:
        return {}
    names = await StockRepository(session).get_names_by_codes(unique)
    if not names:
        return {}

    keys: list[str] = []
    key_owner: list[tuple[str, str]] = []  # (redis_key, code)
    for code in unique:
        for prefix in ("quote:", "quote:eod:"):
            key = f"{prefix}{code}"
            keys.append(key)
            key_owner.append((key, code))
    raw_values = await get_redis().mget(*keys)
    cached: dict[str, dict[str, Any]] = {}
    for (key, code), raw in zip(key_owner, raw_values, strict=True):
        if raw and code not in cached:
            cached[code] = json.loads(raw)

    result: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for code in unique:
        if code not in names:
            continue
        snapshot = cached.get(code) or {}
        price = _to_float(snapshot.get("price"))
        prev_close = _to_float(snapshot.get("prev_close"))
        change_pct = (
            (price - prev_close) / prev_close * 100
            if price is not None and prev_close
            else None
        )
        if change_pct is None:
            missing.append(code)
        result[code] = {
            "name": names[code] or code,
            "change_pct": round(change_pct, 2) if change_pct is not None else None,
        }

    if missing:
        bars = await fetch_daily_bars_multi(session, missing, limit=2)
        for code in missing:
            # fetch_daily_bars_multi 返回升序列表：末位最新，前一根为昨收
            closes = [b.close for b in bars.get(code, []) if b.close is not None]
            change_pct = None
            if len(closes) >= 2 and closes[-2]:
                change_pct = float(
                    round((closes[-1] - closes[-2]) / closes[-2] * 100, 2)
                )
            result[code]["change_pct"] = change_pct
    return result


async def get_stock_sectors(session: AsyncSession, stock_code: str) -> dict[str, Any] | None:
    """获取个股所属行业与概念，附带最新板块资金流。"""
    stock = await get_stock_by_code(session, stock_code)
    if stock is None:
        return None

    sectors: list[dict[str, Any]] = []
    for level, label in (
        (stock.industry_level_1, "industry"),
        (stock.industry_level_2, "industry"),
        (stock.industry_level_3, "industry"),
    ):
        if level:
            sectors.append({"name": level, "type": label})

    concept_repo = StockConceptRepository(session)
    concepts = await concept_repo.get_concepts_by_stock(stock_code)
    for concept in concepts:
        sectors.append({"name": concept.concept_name, "type": "concept"})

    # 用最新板块资金流统计做补充
    latest_date = (
        await sector_fund_flow_repository.latest_trade_date(session)
    ) or today_cn()
    flow_rows = await sector_fund_flow_repository.list_by_date_and_names(
        session, latest_date, [s["name"] for s in sectors]
    )
    flow_by_name = {row.sector_name: row for row in flow_rows}

    enriched = []
    for item in sectors:
        row = flow_by_name.get(item["name"])
        enriched.append(
            {
                "name": item["name"],
                "type": item["type"],
                "change_pct": _to_float(row.change_pct) if row else None,
                "main_net_inflow": _to_float(row.main_net_inflow) if row else None,
            }
        )

    return {
        "code": stock_code,
        "name": stock.stock_name or stock_code,
        "sectors": enriched,
    }
