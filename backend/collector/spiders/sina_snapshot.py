"""新浪批量实时快照（盘中低延迟供数共享函数）。

消费者：盘中自主执行驻留进程（tick 行情）与盘中计划校准采集器（修正单
前置行情）。计划标的为个位数集合，直拉 hq.sinajs.cn 批量接口——
sina_quote cron */5 落库快照对 60s tick 太陈旧。
"""

from typing import Any

import httpx

_SINA_BASE_URL = "https://hq.sinajs.cn"


def _to_sina_symbol(code: str) -> str:
    """6 位代码 → 新浪符号（6 开头沪市 sh，其余深市 sz）。"""
    return ("sh" if code.startswith("6") else "sz") + code


def fetch_sina_quotes(codes: list[str]) -> dict[str, dict[str, Any]]:
    """批量拉取新浪实时快照（阻塞 IO，经 run_in_thread 调用）。

    返回按 6 位代码键控的 ``{name, price, prev_close, change_pct}``；解析失败
    的条目跳过（tick 对缺行情标的不评判）。
    """
    if not codes:
        return {}
    url = f"{_SINA_BASE_URL}/list={','.join(_to_sina_symbol(c) for c in codes)}"
    resp = httpx.get(url, headers={"Referer": "https://finance.sina.com.cn"}, timeout=10.0)
    resp.encoding = "GB18030"
    quotes: dict[str, dict[str, Any]] = {}
    for line in resp.text.splitlines():
        if "=" not in line or '"' not in line:
            continue
        var, payload = line.split("=", 1)
        code = var.strip().split("_")[-1].lstrip("shz")
        parts = payload.strip().strip(';').strip('"').split(",")
        if len(parts) < 4:
            continue
        try:
            price = float(parts[3])
            prev_close = float(parts[2])
        except ValueError:
            continue
        if price <= 0 or prev_close <= 0:
            continue
        quotes[code] = {
            "name": parts[0],
            "price": price,
            "prev_close": prev_close,
            "change_pct": round((price - prev_close) / prev_close * 100, 2),
        }
    return quotes
