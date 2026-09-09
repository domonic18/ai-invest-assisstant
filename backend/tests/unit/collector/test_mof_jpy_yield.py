"""日本财务省日债收益率 spider 单测：fixture 按全量 CSV 真实格式转写。"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.core.constants import GLOBAL_INDEX_CODES
from collector.spiders.mof_jpy_yield import (
    MofJpyYieldCollector,
    parse_jgbcm_all,
    wareki_to_date,
)

# 头两行 + 尾部样例截取自 jgbcm_all.csv 真实响应（1974 年首行 10Y 为 -）
_CSV_SAMPLE = "\r\n".join(
    [
        "国債金利情報,,,,,,,,,,,,,,,(単位 : %)",
        "基準日,1年,2年,3年,4年,5年,6年,7年,8年,9年,10年,15年,20年,25年,30年,40年",
        "S49.9.24,10.327,9.362,8.83,8.515,8.348,8.29,8.24,8.121,8.127,-,-,-,-,-,-",
        "H8.1.4,0.749,0.898,1.082,1.537,1.789,2.006,2.154,2.34,2.507,2.656,3.099,3.472,3.821,3.722,3.829",
        "R8.8.29,1.511,1.75,1.902,2.092,2.241,2.366,2.514,2.68,2.814,2.958,3.513,3.826,4.113,4.101,4.101",
        "R8.9.1,1.49,1.727,1.878,2.067,2.216,2.342,2.489,2.655,2.789,2.933,3.483,3.796,4.081,4.069,4.072",
    ]
)


@pytest.mark.unit
class TestWarekiToDate:
    def test_era_boundaries(self) -> None:
        assert wareki_to_date("S49.9.24") == date(1974, 9, 24)
        assert wareki_to_date("S64.1.7") == date(1989, 1, 7)
        assert wareki_to_date("H1.1.8") == date(1989, 1, 8)
        assert wareki_to_date("H31.4.30") == date(2019, 4, 30)
        assert wareki_to_date("R1.5.7") == date(2019, 5, 7)
        assert wareki_to_date("R8.8.31") == date(2026, 8, 31)

    def test_invalid_text_raises(self) -> None:
        for bad in ["X8.8.31", "2026-08-31", "R8.8", ""]:
            with pytest.raises(ValueError):
                wareki_to_date(bad)


@pytest.mark.unit
class TestParseJgbcmAll:
    def test_parses_ten_year_column_and_skips_missing(self) -> None:
        rows = parse_jgbcm_all(_CSV_SAMPLE, "JP10Y")

        # S49.9.24 的 10Y 为 -，跳过；其余三行有效
        assert [r["trade_date"] for r in rows] == [
            date(1996, 1, 4),
            date(2026, 8, 29),
            date(2026, 9, 1),
        ]
        assert rows[0]["close"] == 2.656
        assert rows[0]["change_pct"] is None
        assert rows[1]["change_pct"] == pytest.approx(11.3705, rel=1e-3)
        assert rows[2]["change_pct"] == pytest.approx(-0.8452, rel=1e-3)
        assert all(r["index_code"] == "JP10Y" and r["source"] == "mof" for r in rows)
        assert rows[1]["open"] is None and rows[1]["volume"] is None

    def test_missing_header_raises(self) -> None:
        with pytest.raises(ValueError, match="基準日"):
            parse_jgbcm_all("no,header\n1,2", "JP10Y")

    def test_missing_ten_year_column_raises(self) -> None:
        with pytest.raises(ValueError, match="10年"):
            parse_jgbcm_all("基準日,1年,2年\nR8.9.1,1.49,1.72", "JP10Y")


@pytest.mark.unit
class TestMofJpyYieldCollector:
    async def test_collect_parses_csv(self) -> None:
        collector = MofJpyYieldCollector(config={"source": "mof"})

        def _download() -> str:
            return _CSV_SAMPLE

        with patch(
            "collector.spiders.mof_jpy_yield._download_all_csv",
            side_effect=_download,
        ):
            items = await collector.collect()

        assert len(items) == 3
        assert {i["index_code"] for i in items} <= set(GLOBAL_INDEX_CODES)

    async def test_truncated_download_raises(self) -> None:
        head = MagicMock()
        head.headers = {"Content-Length": "1176385"}
        body = MagicMock()
        body.content = b"short"
        body.raise_for_status = MagicMock()
        with patch(
            "collector.spiders.mof_jpy_yield.requests.head", return_value=head
        ), patch(
            "collector.spiders.mof_jpy_yield.requests.get", return_value=body
        ):
            with pytest.raises(IOError, match="truncated"):
                MofJpyYieldCollector._collect_sync(
                    MofJpyYieldCollector(config={"source": "mof"}), "JP10Y"
                )
