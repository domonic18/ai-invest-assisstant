"""CME FedWatch 采集器单测：解析逻辑按 QuikStrike 页面 fixture 钉死。

fixture 转写自 2026-09-08 实测响应（Akamai 拦 httpx，结构变化时本套测试
先行失败，修复解析器即可，不做静默空采）。
"""

from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from collector.spiders.cme_fed_watch import (
    CmeFedWatchCollector,
    extract_hidden_fields,
    extract_session_cache,
    parse_current_range,
    parse_data_as_at,
    parse_probabilities,
    validate_probabilities,
)

_FIXTURES = Path(__file__).parents[2] / "fixtures"


def _load(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def _resp(text: str) -> MagicMock:
    response = MagicMock()
    response.text = text
    return response


@pytest.mark.unit
class TestExtractSessionCache:
    def test_extracts_and_unescapes(self) -> None:
        page = _load("fedwatch_entry.html")
        assert extract_session_cache(page) == "insid=243409112&qsid=d4f701d0"

    def test_missing_raises(self) -> None:
        with pytest.raises(ValueError, match="global_instanceCache"):
            extract_session_cache("<html><body>no cache</body></html>")


@pytest.mark.unit
class TestParseDataAsAt:
    def test_parses_ct_timestamp(self) -> None:
        data_as_at, as_of = parse_data_as_at(_load("fedwatch_current.html"))
        assert data_as_at == datetime(2026, 9, 7, 11, 37, 58, tzinfo=timezone.utc)
        assert as_of == date(2026, 9, 7)

    def test_missing_raises(self) -> None:
        with pytest.raises(ValueError, match="Data as of"):
            parse_data_as_at("<html></html>")


@pytest.mark.unit
class TestParseCurrentRange:
    def test_parses_marker(self) -> None:
        assert parse_current_range(_load("fedwatch_current.html")) == (350, 375)

    def test_missing_raises(self) -> None:
        with pytest.raises(ValueError, match="current target range"):
            parse_current_range("<html></html>")


@pytest.mark.unit
class TestExtractHiddenFields:
    def test_collects_hidden_inputs_in_any_attr_order(self) -> None:
        payload = extract_hidden_fields(_load("fedwatch_current.html"))
        assert payload["__VIEWSTATE"] == "/wEPDwUENTI4Mw9nF39mZGRmZmQ="
        assert payload["__EVENTVALIDATION"] == "/wEdAAKSkYlg3A=="

    def test_input_without_value_yields_empty(self) -> None:
        payload = extract_hidden_fields('<input type="hidden" name="foo">')
        assert payload == {"foo": ""}


@pytest.mark.unit
class TestParseProbabilities:
    def test_parses_meeting_rows_and_skips_empty_cells(self) -> None:
        rows = parse_probabilities(_load("fedwatch_ptree.html"))

        # 4 会议 × 8 区间，9/16 行尾空 cell 跳过 → 31 行
        assert len(rows) == 31
        assert {r["meeting_date"] for r in rows} == {
            date(2026, 9, 16),
            date(2026, 10, 28),
            date(2026, 12, 9),
            date(2027, 1, 27),
        }
        sep16 = [r for r in rows if r["meeting_date"] == date(2026, 9, 16)]
        by_low = {r["range_low"]: r for r in sep16}
        assert by_low[350]["probability"] == 39.6
        assert by_low[375]["probability"] == 60.4
        assert by_low[350]["range_high"] == 375
        assert 500 not in by_low  # 尾部空 cell 不产行

    def test_missing_table_raises(self) -> None:
        with pytest.raises(ValueError, match="Conditional Meeting Probabilities"):
            parse_probabilities("<html><body>no table</body></html>")

    def test_missing_meeting_header_raises(self) -> None:
        page = "<table><tr><td>Conditional Meeting Probabilities</td></tr></table>"
        with pytest.raises(ValueError, match="Meeting Date"):
            parse_probabilities(page)


@pytest.mark.unit
class TestValidateProbabilities:
    def test_fixture_rows_pass(self) -> None:
        rows = parse_probabilities(_load("fedwatch_ptree.html"))
        validate_probabilities(rows)  # 每会议和均 ~100，不抛错

    def test_misaligned_columns_rejected(self) -> None:
        rows = [
            {"meeting_date": date(2026, 9, 16), "range_low": 350,
             "range_high": 375, "probability": 39.6},
            {"meeting_date": date(2026, 9, 16), "range_low": 375,
             "range_high": 400, "probability": 20.0},
        ]
        with pytest.raises(ValueError, match="sum to"):
            validate_probabilities(rows + _fixture_rows_excluding(date(2026, 9, 16)))

    def test_truncated_table_rejected(self) -> None:
        rows = [
            {"meeting_date": date(2026, 9, 16), "range_low": 350,
             "range_high": 375, "probability": 100.0},
        ]
        with pytest.raises(ValueError, match="truncated"):
            validate_probabilities(rows)

    def test_degenerate_single_column_rejected(self) -> None:
        # 生产事故回放（2026-09-09 08:41 CST 补跑）：夜间态页面仅剩
        # 一列 475-500=100%，每会议和恒 100、会议数达标，靠区间列数拦截
        rows = [
            {"meeting_date": meeting, "range_low": 475,
             "range_high": 500, "probability": 100.0}
            for meeting in (
                date(2026, 9, 16),
                date(2026, 10, 28),
                date(2026, 12, 9),
                date(2027, 1, 27),
            )
        ]
        with pytest.raises(ValueError, match="degenerate"):
            validate_probabilities(rows)


def _fixture_rows_excluding(meeting_date: date) -> list[dict[str, object]]:
    return [
        row
        for row in parse_probabilities(_load("fedwatch_ptree.html"))
        if row["meeting_date"] != meeting_date
    ]


@pytest.mark.unit
class TestCmeFedWatchCollector:
    async def test_collect_full_chain(self) -> None:
        collector = CmeFedWatchCollector(config={"source": "cme"})
        with patch(
            "collector.spiders.cme_fed_watch.chrome_get",
            side_effect=[
                _resp(_load("fedwatch_entry.html")),
                _resp(_load("fedwatch_current.html")),
            ],
        ), patch(
            "collector.spiders.cme_fed_watch.chrome_post",
            return_value=_resp(_load("fedwatch_ptree.html")),
        ) as mock_post:
            items = await collector.collect()

        assert len(items) == 31
        assert all(i["as_of_date"] == date(2026, 9, 7) for i in items)
        assert collector._snapshot == {
            "as_of_date": date(2026, 9, 7),
            "data_as_at": datetime(2026, 9, 7, 11, 37, 58, tzinfo=timezone.utc),
            "current_range_low": 350,
            "current_range_high": 375,
        }
        # postback 载荷：隐藏字段 + lbPTree 事件目标
        payload = mock_post.call_args.kwargs["data"]
        assert payload["__EVENTTARGET"].endswith("$lbPTree")
        assert payload["__EVENTARGUMENT"] == ""
        assert "__VIEWSTATE" in payload

    async def test_empty_table_raises_no_silent_skip(self) -> None:
        collector = CmeFedWatchCollector(config={"source": "cme"})
        empty_tree = (
            '<html><body><table>'
            '<tr><td colspan="9">CME FedWatch Tool - '
            'Conditional Meeting Probabilities</td></tr>'
            '<tr><th>Meeting Date</th><th>350-375</th></tr>'
            '</table></body></html>'
        )
        with patch(
            "collector.spiders.cme_fed_watch.chrome_get",
            side_effect=[
                _resp(_load("fedwatch_entry.html")),
                _resp(_load("fedwatch_current.html")),
            ],
        ), patch(
            "collector.spiders.cme_fed_watch.chrome_post",
            return_value=_resp(empty_tree),
        ):
            with pytest.raises(ValueError, match="empty"):
                await collector.collect()
