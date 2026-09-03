"""财联社投资日历采集器测试（响应结构按探针实测转写）。"""

import hashlib
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.core.clock import CN_TZ
from collector.spiders import cls_investkalendar
from collector.spiders.cls_investkalendar import (
    ClsInvestkalendarCollector,
    _map_item,
    _parse_calendar_time,
    fetch_calendar,
)

_PROBE_PAYLOAD = {
    "code": 200,
    "data": [
        {
            "calendar_day": "2026-09-03",
            "week": "星期四",
            "items": [
                {
                    "id": 892551,
                    "calendar_time": "2026-09-03 00:00:00",
                    "data_id": 23676,
                    "type": 2,
                    "mark_red": 0,
                    "economic": None,
                    "event": {
                        "title": "大会",
                        "country": "中国",
                        "country_icon": "",
                        "star": 5,
                    },
                    "holiday": None,
                    "title": "2026世界动力电池大会将于9月3日至4日在四川宜宾举办",
                },
                {
                    "id": 889650,
                    "calendar_time": "2026-09-03 17:00:00",
                    "data_id": 68732,
                    "type": 1,
                    "mark_red": 0,
                    "economic": {
                        "title": "欧元区7月PPI年率(%)",
                        "country": "欧元区",
                        "star": 2,
                        "indicator_id": 45153,
                        "indicator_period": "7月",
                        "front": "4.6",
                        "fix": "--",
                        "consensus": "5.3",
                        "actual": "--",
                        "unit": "%",
                        "flag": "--",
                    },
                    "event": None,
                    "holiday": None,
                    "title": "欧元区7月PPI年率(%)",
                },
                {
                    "id": 3,
                    "calendar_time": "2026-09-04 09:30:00",
                    "type": 3,
                    "title": "新股申购（独立接口，本轮无映射）",
                },
            ],
        },
        {"calendar_day": "2026-09-04", "week": "星期五", "items": []},
        {"calendar_day": "bad-day", "items": "not-a-list"},
    ],
}


def _response(payload: dict) -> MagicMock:
    response = MagicMock()
    response.json.return_value = payload
    return response


def _cn_to_utc(calendar_time: str) -> datetime:
    return datetime.strptime(calendar_time, "%Y-%m-%d %H:%M:%S").replace(
        tzinfo=CN_TZ
    ).astimezone(timezone.utc)


@pytest.mark.unit
class TestHelpers:
    def test_parse_calendar_time_converts_cn_to_utc(self) -> None:
        event_time = _parse_calendar_time("2026-09-03 17:00:00")
        assert event_time == _cn_to_utc("2026-09-03 17:00:00")
        assert event_time.tzinfo is not None

    def test_source_hash_format(self) -> None:
        event_time = _cn_to_utc("2026-09-03 00:00:00")
        expected = hashlib.md5(
            f"cls|{event_time.isoformat()}|标题".encode()
        ).hexdigest()
        assert (
            cls_investkalendar._source_hash(event_time, "标题") == expected
        )

    def test_map_item_economic_to_macro(self) -> None:
        row = _map_item(_PROBE_PAYLOAD["data"][0]["items"][1])
        assert row is not None
        assert row["category"] == "宏观"
        assert row["title"] == "欧元区7月PPI年率(%)"
        assert row["event_time"] == _cn_to_utc("2026-09-03 17:00:00")
        assert row["source"] == "cls"
        assert row["source_url"] == "https://www.cls.cn/investkalendar"
        assert row["end_time"] is None
        assert row["impact_markets"] is None
        assert row["related_symbols"] is None
        assert row["source_hash"] == cls_investkalendar._source_hash(
            row["event_time"], row["title"]
        )

    def test_map_item_event_to_conference(self) -> None:
        row = _map_item(_PROBE_PAYLOAD["data"][0]["items"][0])
        assert row is not None
        assert row["category"] == "会议"

    def test_map_item_skips_unmapped_and_invalid(self) -> None:
        items = _PROBE_PAYLOAD["data"][0]["items"]
        assert _map_item(items[2]) is None  # 未知 type
        assert _map_item({"type": 1, "calendar_time": "2026-09-03 10:00:00"}) is None
        assert _map_item({"type": 1, "title": "无时间"}) is None

    def test_map_item_truncates_long_title(self) -> None:
        row = _map_item(
            {"type": 2, "calendar_time": "2026-09-03 10:00:00", "title": "长" * 400}
        )
        assert row is not None
        assert len(row["title"]) == 300


@pytest.mark.unit
class TestFetchCalendar:
    async def test_maps_and_flattens_days(self) -> None:
        session = MagicMock()
        session.get.return_value = _response(_PROBE_PAYLOAD)
        with patch.object(
            cls_investkalendar, "shared_session", return_value=session
        ):
            rows = fetch_calendar(1788425675)

        assert len(rows) == 2  # type=3 与坏分组被过滤
        assert {row["category"] for row in rows} == {"宏观", "会议"}
        params = session.get.call_args.kwargs["params"]
        assert params["tradeDate"] == "1788425675"
        assert params["sv"] == "8.7.9"
        assert "sign" in params
        session.get.assert_called_once_with(
            "https://www.cls.cn/api/calendar/web/list",
            params=params,
            timeout=15,
        )

    async def test_non_200_code_raises(self) -> None:
        session = MagicMock()
        session.get.return_value = _response({"code": 403, "msg": "forbidden"})
        with patch.object(
            cls_investkalendar, "shared_session", return_value=session
        ):
            with pytest.raises(RuntimeError, match="code=403"):
                fetch_calendar(1788425675)

    async def test_empty_window(self) -> None:
        session = MagicMock()
        session.get.return_value = _response({"code": 200, "data": []})
        with patch.object(
            cls_investkalendar, "shared_session", return_value=session
        ):
            assert fetch_calendar(1788425675) == []


@pytest.mark.unit
class TestCollector:
    async def test_collect_warms_session_and_delegates(self) -> None:
        collector = ClsInvestkalendarCollector(
            {"source": "cls", "data_type": "invest_calendar"}
        )
        with (
            patch.object(cls_investkalendar, "warm_session") as mock_warm,
            patch.object(
                cls_investkalendar,
                "fetch_calendar",
                return_value=[{"source_hash": "h1"}],
            ) as mock_fetch,
        ):
            rows = await collector.collect()
        assert rows == [{"source_hash": "h1"}]
        mock_warm.assert_called_once()
        assert mock_fetch.call_count == 1

    async def test_store_contract_do_nothing(self) -> None:
        collector = ClsInvestkalendarCollector(
            {"source": "cls", "data_type": "invest_calendar"}
        )
        assert collector.table == "calendar_event"
        assert collector.conflict_key == "source_hash"
        assert collector.update_columns is None
