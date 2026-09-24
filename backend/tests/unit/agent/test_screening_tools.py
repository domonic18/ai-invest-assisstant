"""screening_tools 单测：工具薄壳的叙述文本、事件搭车与错误透传。

查询与整形的单测在 ``tests/unit/services/test_iwencai_service.py``。
"""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.tools import screening_tools as st
from app.services.market.iwencai_service import IwencaiError

pytestmark = pytest.mark.unit


def _screen_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "query": "市盈率<20",
        "total": 2,
        "truncated": False,
        "columns": ["最新价", "涨跌幅"],
        "stocks": [
            {"stockCode": "000523", "stockName": "广州浪奇", "最新价": 3.21, "涨跌幅": 5.2},
            {"stockCode": "600000", "stockName": "浦发银行", "最新价": 8.9, "涨跌幅": -1.3},
        ],
        "chunks_info": [],
    }
    payload.update(overrides)
    return payload


async def test_screen_stocks_emits_event_with_payload() -> None:
    screen_mock = AsyncMock(return_value=_screen_payload())
    with patch.object(st.iwencai_service, "screen", screen_mock):
        result = await st.screen_stocks.ainvoke({"query": "市盈率<20"})

    event = result["__event__"]
    assert event["type"] == "stock_screening.complete"
    assert event["total"] == 2
    assert event["truncated"] is False
    assert event["columns"] == ["最新价", "涨跌幅"]
    assert event["stocks"][0]["stockCode"] == "000523"
    assert "同花顺问财" in result["summary"]
    screen_mock.assert_awaited_once_with("市盈率<20", limit=30)


async def test_screen_stocks_truncated_summary() -> None:
    screen_mock = AsyncMock(return_value=_screen_payload(total=200, truncated=True))
    with patch.object(st.iwencai_service, "screen", screen_mock):
        result = await st.screen_stocks.ainvoke({"query": "市值从小到大", "limit": 100})

    assert result["truncated"] is True
    assert "前 100" in result["summary"]
    assert "收敛" in result["summary"]


async def test_screen_stocks_empty_result_guidance() -> None:
    screen_mock = AsyncMock(
        return_value=_screen_payload(total=0, truncated=False, columns=[], stocks=[])
    )
    with patch.object(st.iwencai_service, "screen", screen_mock):
        result = await st.screen_stocks.ainvoke({"query": "申万一级行业指数"})

    assert "未命中" in result["summary"]
    assert "显式年份" in result["summary"]


async def test_screen_stocks_error_passthrough() -> None:
    screen_mock = AsyncMock(side_effect=IwencaiError("问财网关请求失败：超时"))
    with patch.object(st.iwencai_service, "screen", screen_mock):
        result = await st.screen_stocks.ainvoke({"query": "市盈率<20"})

    assert result == {"error": "问财网关请求失败：超时"}
