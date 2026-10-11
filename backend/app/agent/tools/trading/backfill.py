"""交易 Agent 数据补采工具：个股财务报表按股补采（行情补采复用 collect_market_data）。

``eastmoney_financial_statement`` spider 原生接受 ``symbols``（缺省采全部自选股），
``collector/runtime/runner.py`` 对任意任务统一接受 ``symbols`` 参数——按股派发
无需改任务声明表。任务异步执行：派发后须等待数据入库，再重新调用查询工具验证。
"""

import re
from typing import Any

import structlog
from langchain_core.tools import tool

logger = structlog.get_logger(__name__)

FINANCIAL_MAX_CODES = 10

_CODE_RE = re.compile(r"\d{6}")


@tool
async def collect_financial_data(stock_codes: list[str]) -> dict[str, Any]:
    """补采指定个股的财务报表数据（资产负债表/利润表/现金流量表三大报表）。

    查询工具发现个股财务数据缺失或滞后时用于数据自愈。任务异步执行：派发后
    须等待数据入库（约 1-2 分钟/只），再重新调用 query_financial_data 验证。

    Args:
        stock_codes: 6 位股票代码列表（如 ["000001", "600519"]），单次最多
            10 只，超出部分不派发（可再次调用补齐）。
    """
    from app.core.database import AsyncSessionLocal
    from collector.runtime.dispatcher import dispatch_collector_task

    codes: list[str] = []
    invalid: list[str] = []
    for raw in stock_codes:
        code = str(raw).strip()
        if _CODE_RE.fullmatch(code):
            if code not in codes:
                codes.append(code)
        else:
            invalid.append(code)
    if invalid:
        return {"error": f"股票代码须为 6 位数字，非法代码：{invalid}"}
    if not codes:
        return {"error": "stock_codes 不能为空"}

    truncated = len(codes) > FINANCIAL_MAX_CODES
    codes = codes[:FINANCIAL_MAX_CODES]
    try:
        async with AsyncSessionLocal() as session:
            await dispatch_collector_task(
                session, "financial-statement", {"symbols": codes}
            )
    except Exception:  # noqa: BLE001
        # 意外异常可能携带内部细节（连接串/SQL），不直接喂给 LLM。
        logger.exception("financial_data_collect_trigger_failed", symbols=codes)
        return {"error": "财务报表补采任务派发失败，请稍后重试或检查采集服务状态"}

    note = (
        "财务报表补采任务已提交（异步执行，约 1-2 分钟/只）；"
        "请稍后重新调用 query_financial_data 验证数据。"
    )
    if truncated:
        note += f" 本次仅派发前 {FINANCIAL_MAX_CODES} 只，其余请再次调用本工具补齐。"
    return {"symbols": codes, "note": note}
