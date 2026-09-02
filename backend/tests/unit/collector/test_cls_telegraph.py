"""财联社电报采集器测试（响应结构按探针实测转写）。"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from collector.spiders import cls_telegraph
from collector.spiders.cls_telegraph import (
    ClsTelegraphCollector,
    _level_to_importance,
    _stock_codes,
    fetch_page,
)

_PROBE_PAYLOAD = {
    "errno": 0,
    "data": {
        "roll_data": [
            {
                "id": 1899921,
                "title": "快讯标题",
                "brief": "摘要",
                "content": "<p>正文</p>",
                "ctime": 1785696000,
                "type": "公司",
                "level": "A",
                "shared": -1,
                "stock_list": [
                    {"StockID": "sz300750", "name": "宁德时代", "Change": 1.5},
                    {"name": "缺代码"},
                ],
                "shareurl": "https://www.cls.cn/detail/1899921",
                "modified_time": 1785696100,
                "subjects": [{"subject_name": "锂电池"}],
            },
            {
                "id": 1899920,
                "content": "无标题快讯",
                "ctime": 1785695000,
                "type": "宏观",
                "level": "",
            },
        ]
    },
}


def _response(payload: dict) -> MagicMock:
    response = MagicMock()
    response.json.return_value = payload
    return response


@pytest.fixture(autouse=True)
def _fresh_session():
    cls_telegraph.reset_session()
    yield
    cls_telegraph.reset_session()


@pytest.mark.unit
class TestHelpers:
    def test_level_to_importance(self) -> None:
        assert _level_to_importance("A") == 3
        assert _level_to_importance("B") == 2
        assert _level_to_importance("C") == 1
        assert _level_to_importance("10") == 10
        assert _level_to_importance(7) == 7
        assert _level_to_importance("") is None
        assert _level_to_importance(None) is None
        assert _level_to_importance("X") is None

    def test_stock_codes(self) -> None:
        assert _stock_codes([{"StockID": "sz300750"}]) == ["sz300750"]
        assert _stock_codes([{"name": "缺代码"}]) is None
        assert _stock_codes("bad") is None
        assert _stock_codes(None) is None


@pytest.mark.unit
class TestFetchPage:
    async def test_maps_items(self) -> None:
        session = MagicMock()
        session.get.return_value = _response(_PROBE_PAYLOAD)
        with (
            patch.object(cls_telegraph, "_get_session", return_value=session),
            patch.object(cls_telegraph, "_sv", "8.7.9"),
        ):
            rows = fetch_page(last_time=0, rn=20)

        assert len(rows) == 2
        first = rows[0]
        assert first["cls_msg_id"] == 1899921
        assert first["title"] == "快讯标题"
        assert first["content"] == "<p>正文</p>"
        assert first["category"] == "公司"
        assert first["importance"] == 3
        assert first["shared"] == -1
        assert first["stock_codes"] == ["sz300750"]
        assert json.loads(first["extra"])["brief"] == "摘要"
        assert json.loads(first["extra"])["shareurl"] == "https://www.cls.cn/detail/1899921"
        assert first["publish_time"] == datetime.fromtimestamp(
            1785696000, tz=timezone.utc
        )
        assert first["publish_time"].tzinfo is not None

        second = rows[1]
        assert second["title"] is None
        assert second["importance"] is None
        assert second["stock_codes"] is None
        assert second["extra"] is None
        assert second["publish_time"] == datetime.fromtimestamp(
            1785695000, tz=timezone.utc
        )

        # 请求参数：签名 + sv
        call_kwargs = session.get.call_args.kwargs
        params = call_kwargs["params"]
        assert params["last_time"] == "0"
        assert params["rn"] == "20"
        assert params["sv"] == "8.7.9"
        assert "sign" in params
        session.get.assert_called_once_with(
            "https://www.cls.cn/v1/roll/get_roll_list",
            params=params,
            timeout=15,
        )

    async def test_pagination_last_time(self) -> None:
        session = MagicMock()
        session.get.return_value = _response({"errno": 0, "data": {"roll_data": []}})
        with (
            patch.object(cls_telegraph, "_get_session", return_value=session),
            patch.object(cls_telegraph, "_sv", "8.7.9"),
        ):
            assert fetch_page(last_time=1785695000, rn=20) == []
        params = session.get.call_args.kwargs["params"]
        assert params["last_time"] == "1785695000"

    async def test_errno_non_zero_raises(self) -> None:
        session = MagicMock()
        session.get.return_value = _response({"errno": 403, "errmsg": "forbidden"})
        with (
            patch.object(cls_telegraph, "_get_session", return_value=session),
            patch.object(cls_telegraph, "_sv", "8.7.9"),
        ):
            with pytest.raises(RuntimeError, match="errno=403"):
                fetch_page()


@pytest.mark.unit
class TestWarmAndReset:
    async def test_warm_updates_sv(self) -> None:
        session = MagicMock()
        page = MagicMock()
        page.text = 'var cfg={sv:"9.9.9"}'
        page.raise_for_status.return_value = None
        session.get.side_effect = [page, _response(_PROBE_PAYLOAD)]
        with patch.object(cls_telegraph, "_get_session", return_value=session):
            assert cls_telegraph.warm_session() == "9.9.9"
            rows = fetch_page()
        params = session.get.call_args.kwargs["params"]
        assert params["sv"] == "9.9.9"
        assert len(rows) == 2

    async def test_reset_restores_default_sv(self) -> None:
        cls_telegraph._sv = "9.9.9"
        cls_telegraph.reset_session()
        assert cls_telegraph._sv == cls_telegraph.DEFAULT_SV


@pytest.mark.unit
class TestCollector:
    async def test_collect_delegates_to_fetch_page(self) -> None:
        collector = ClsTelegraphCollector(
            {"source": "cls", "data_type": "news_telegraph"}
        )
        with patch.object(
            cls_telegraph, "fetch_page", return_value=[{"cls_msg_id": 1}]
        ) as mock_fetch:
            items = await collector.collect(rn=10)
        assert items == [{"cls_msg_id": 1}]
        mock_fetch.assert_called_once_with(0, 10)

    async def test_store_contract_do_nothing(self) -> None:
        collector = ClsTelegraphCollector(
            {"source": "cls", "data_type": "news_telegraph"}
        )
        assert collector.table == "news_telegraph"
        assert collector.conflict_key == "cls_msg_id"
        assert collector.update_columns is None
