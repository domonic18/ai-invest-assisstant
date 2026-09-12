"""iwencai_service.screen() 整形单测：代码归一、列派生、截断与放宽改写传参。"""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.services.market import iwencai_service as isvc
from app.services.market.iwencai_service import (
    _derive_columns,
    _normalize_code,
    _relaxed_rewrites,
)

pytestmark = pytest.mark.unit


def test_normalize_code() -> None:
    assert _normalize_code("000523.SZ") == "000523"
    assert _normalize_code("600000.SH") == "600000"
    assert _normalize_code("000523") == "000523"


def test_relaxed_rewrites() -> None:
    assert _relaxed_rewrites("市盈率<20，非ST，非北交所，近月有涨停") == ["市盈率<20，近月有涨停"]
    assert _relaxed_rewrites("非ST且净利润大于0") == ["净利润大于0"]
    assert _relaxed_rewrites("市盈率<20") == []


def test_derive_columns_excludes_fixed_and_keeps_order() -> None:
    rows = [
        {"股票代码": "1", "股票简称": "a", "最新价": 1.0, "涨跌幅": 2.0},
        {"涨跌幅": 3.0, "换手率": 5.0},
    ]
    assert _derive_columns(rows) == ["最新价", "涨跌幅", "换手率"]


def _stub_query2data(datas: list[dict[str, Any]], code_count: int | None = None) -> AsyncMock:
    mock = AsyncMock(
        return_value={
            "datas": datas,
            "code_count": len(datas) if code_count is None else code_count,
            "chunks_info": [],
        }
    )
    return mock


async def test_screen_normalizes_and_shapes_payload() -> None:
    mock = _stub_query2data(
        [
            {"股票代码": "000523.SZ", "股票简称": "广州浪奇", "最新价": 3.21, "涨跌幅": 5.2},
            {"股票代码": "600000.SH", "股票简称": "浦发银行", "最新价": 8.9, "涨跌幅": -1.3},
        ],
        code_count=2,
    )
    with patch.object(isvc, "query2data", mock):
        payload = await isvc.screen("市盈率<20")

    assert payload["query"] == "市盈率<20"
    assert payload["total"] == 2
    assert payload["truncated"] is False
    assert payload["columns"] == ["最新价", "涨跌幅"]
    assert payload["stocks"][0] == {
        "stockCode": "000523",
        "stockName": "广州浪奇",
        "最新价": 3.21,
        "涨跌幅": 5.2,
    }
    assert payload["chunks_info"] == []


async def test_screen_truncates_to_100_rows() -> None:
    datas = [
        {"股票代码": f"{i:06d}.SZ", "股票简称": f"股票{i}", "最新价": 1.0}
        for i in range(120)
    ]
    mock = _stub_query2data(datas, code_count=120)
    with patch.object(isvc, "query2data", mock):
        payload = await isvc.screen("市值从小到大")

    assert len(payload["stocks"]) == 100
    assert payload["truncated"] is True
    assert payload["total"] == 120


async def test_screen_passes_relaxed_rewrites_and_clamps_limit() -> None:
    mock = _stub_query2data([{"股票代码": "000001.SZ", "股票简称": "平安银行"}])
    with patch.object(isvc, "query2data", mock):
        await isvc.screen("市盈率<20，非ST", limit=999)

    kwargs = mock.await_args.kwargs
    assert kwargs["limit"] == 100
    assert kwargs["rewrite_candidates"] == ["市盈率<20"]


async def test_screen_total_falls_back_to_row_count() -> None:
    mock = _stub_query2data([{"股票代码": "000001.SZ", "股票简称": "平安银行"}], code_count=0)
    with patch.object(isvc, "query2data", mock):
        payload = await isvc.screen("市盈率<20")

    assert payload["total"] == 1
