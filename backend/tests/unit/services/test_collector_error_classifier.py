"""采集错误归因分类器单测：用本地库实证错误原文钉归因。"""

import pytest

from app.services.collector.health.error_classifier import (
    CAUSE_LABELS,
    classify_error,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("expected", "error_msg"),
    [
        # WAF/反爬：反爬页 HTML、东财 push2 主机连败
        ("waf", "Can not decode value starting with character '<'"),
        ("waf", "[sina] No value to decode"),
        (
            "waf",
            "[eastmoney] HTTPSConnectionPool(host='push2his.eastmoney.com', "
            "port=443): Max retries exceeded with url: /api/qt/stock/kline/get",
        ),
        ("waf", "httpx.HTTPStatusError: Client error '403 Forbidden'"),
        # 网络层
        ("network", "[sina] Timeout connecting to server"),
        ("network", "('Unknown identifier', 'connecting')"),
        (
            "network",
            "HTTPConnectionPool(host='vip.stock.finance.sina.com.cn', port=80): "
            "Max retries exceeded with url: /quotes_service/api/json_v2.php",
        ),
        (
            "network",
            "('Connection aborted.', RemoteDisconnected('Remote end closed "
            "connection without response'))",
        ),
        # 任务超时
        ("timeout", "SoftTimeLimitExceeded(): Task exceeded soft time limit"),
        # 输入未就绪
        ("not_ready", "2026-09-10 重跑后仍缺日 K：sh510300"),
        ("not_ready", "ReviewInputDataNotReadyError: 复盘输入数据未就绪"),
        # 接口/解析
        ("parse", "KeyError: 'f1043'"),
        ("parse", "json.decoder.JSONDecodeError: Expecting ',' delimiter"),
        # 认证/配额
        ("auth", "Unauthorized: invalid api_key"),
        # 兜底
        ("other", "Native library not available at /app/.venv/lib/py_mini_racer"),
        ("other", "渠道没有任务 concept-constituents 对应的采集器"),
    ],
)
def test_classify_error(expected: str, error_msg: str):
    assert classify_error(error_msg) == expected


def test_classify_error_empty():
    assert classify_error(None) == "other"
    assert classify_error("") == "other"


def test_cause_labels_complete():
    """7 类归因都有中文文案（渠道视图归因 chips 用）。"""
    assert len(CAUSE_LABELS) == 7
    assert set(CAUSE_LABELS.values()) == {
        "WAF/反爬",
        "网络/超时",
        "接口/解析",
        "认证/配额",
        "任务超时",
        "输入未就绪",
        "其他",
    }
