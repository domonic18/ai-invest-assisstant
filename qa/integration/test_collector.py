"""采集渠道回归：逐渠道触发任务并验证执行成功。

覆盖 TASK_MAP 中每个渠道的至少一个任务（含 eastmoney→ths 备用渠道），
通过 POST /admin/collector/tasks/{task}/run 派发，轮询 collector_log 断言终态。

注意：
- 非交易日（周末/节假日）部分行情类任务可能成功但 records_count=0，
  因此只有日期不敏感的任务断言 records_count>0；日期敏感任务锚定最近
  工作日，避免周末空数据干扰。
- preferred_source 仅是"优先渠道"，失败时会按优先级 fallback——任务成功
  但实际渠道不同说明优先渠道降级，记为 warning 而非失败。
"""

import warnings
from datetime import date, timedelta
from typing import Any

import httpx
import pytest

from integration.conftest import API_V1, run_task_and_wait


def _last_weekday() -> str:
    """最近一个工作日（周一~周五），用于交易日敏感的任务参数。"""
    day = date.today()
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day.isoformat()


_TRADING_DAY = _last_weekday()

# (task_name, params, expect_records, timeout_seconds)
CORE_TASK_CASES: list[tuple[str, dict[str, Any], bool, float]] = [
    # sina 渠道
    ("stock-list", {"preferred_source": "sina"}, True, 240),
    ("quote", {"preferred_source": "sina", "symbols": ["000001"]}, True, 180),
    ("kline", {"preferred_source": "sina", "symbols": ["000001"]}, True, 180),
    ("news", {"preferred_source": "sina", "symbols": ["000001"]}, False, 120),
    ("macro", {"preferred_source": "sina"}, True, 240),
    ("auction", {"preferred_source": "sina", "symbols": ["000001"]}, False, 120),
    # eastmoney 渠道
    ("fund-flow", {"preferred_source": "eastmoney", "symbols": ["000001"]}, True, 120),
    ("sector-fund-flow", {"preferred_source": "eastmoney"}, True, 120),
    (
        "dragon-list",
        {
            "preferred_source": "eastmoney",
            "start_date": _TRADING_DAY,
            "end_date": _TRADING_DAY,
        },
        False,
        120,
    ),
    (
        "limit-up-pool",
        {"preferred_source": "eastmoney", "trade_date": _TRADING_DAY},
        False,
        120,
    ),
    # ths 备用渠道
    ("kline", {"preferred_source": "ths", "symbols": ["000001"]}, True, 180),
    ("sector-fund-flow", {"preferred_source": "ths"}, True, 120),
    ("auction", {"preferred_source": "ths", "symbols": ["000001"]}, False, 120),
    # cninfo 渠道
    ("company-profile", {"preferred_source": "cninfo", "symbols": ["000001"]}, True, 120),
    ("ipo-info", {"preferred_source": "cninfo"}, False, 180),
    ("disclosure", {"preferred_source": "cninfo", "symbols": ["000001"]}, False, 180),
]

SLOW_TASK_CASES: list[tuple[str, dict[str, Any], bool, float]] = [
    ("research-report", {"preferred_source": "eastmoney", "symbols": ["000001"]}, False, 180),
    ("fund-holdings", {"preferred_source": "eastmoney", "report_date": "20250331"}, False, 180),
    ("financial-report", {"preferred_source": "eastmoney", "symbols": ["000001"]}, False, 300),
]


def _case_id(case: tuple[str, dict[str, Any], bool, float]) -> str:
    source = case[1].get("preferred_source", "auto")
    return f"{case[0]}@{source}"


class TestCollectorChannels:
    """渠道配置与解析。"""

    def test_default_channels_seeded(self, admin_client: httpx.Client) -> None:
        response = admin_client.get(f"{API_V1}/admin/collector/channels")
        assert response.status_code == 200
        sources = {channel["source"] for channel in response.json()}
        assert {"sina", "eastmoney", "ths", "cninfo"} <= sources

    @pytest.mark.parametrize(
        "task_name,expected_sources",
        [
            ("kline", {"sina", "ths"}),
            ("sector-fund-flow", {"eastmoney", "ths"}),
            ("company-profile", {"cninfo"}),
            ("fund-flow", {"eastmoney"}),
        ],
    )
    def test_task_channels_resolved(
        self,
        admin_client: httpx.Client,
        task_name: str,
        expected_sources: set[str],
    ) -> None:
        response = admin_client.get(
            f"{API_V1}/admin/collector/tasks/{task_name}/channels"
        )
        assert response.status_code == 200
        body = response.json()
        available = {channel["source"] for channel in body["channels"]}
        assert expected_sources <= available
        assert body["resolved_source"] in expected_sources


class TestCollectorTasks:
    """逐渠道任务执行回归。"""

    @pytest.mark.parametrize(
        "task_name,params,expect_records,timeout",
        CORE_TASK_CASES,
        ids=[_case_id(case) for case in CORE_TASK_CASES],
    )
    def test_core_task(
        self,
        admin_client: httpx.Client,
        task_name: str,
        params: dict[str, Any],
        expect_records: bool,
        timeout: float,
    ) -> None:
        entry = run_task_and_wait(admin_client, task_name, params, timeout=timeout)
        assert entry["status"] in ("success", "partial"), (
            f"{task_name} 失败: {entry.get('error_msg')}"
        )
        if entry["source"] != params["preferred_source"]:
            warnings.warn(
                f"{task_name}: 优先渠道 {params['preferred_source']} 降级，"
                f"fallback 到 {entry['source']}: {entry.get('error_msg')}",
                UserWarning,
                stacklevel=1,
            )
        if expect_records:
            assert entry["records_count"] > 0, (
                f"{task_name} 成功但 records_count=0"
            )

    @pytest.mark.slow
    @pytest.mark.parametrize(
        "task_name,params,expect_records,timeout",
        SLOW_TASK_CASES,
        ids=[_case_id(case) for case in SLOW_TASK_CASES],
    )
    def test_slow_task(
        self,
        admin_client: httpx.Client,
        task_name: str,
        params: dict[str, Any],
        expect_records: bool,
        timeout: float,
    ) -> None:
        entry = run_task_and_wait(admin_client, task_name, params, timeout=timeout)
        assert entry["status"] in ("success", "partial"), (
            f"{task_name} 失败: {entry.get('error_msg')}"
        )
        if expect_records:
            assert entry["records_count"] > 0
