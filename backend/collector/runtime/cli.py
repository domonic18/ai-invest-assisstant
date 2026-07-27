"""Collector CLI 入口：python -m collector.runtime.cli <task> [options]。"""

import argparse
import asyncio

from collector.core.logging import configure_logging
from collector.runtime.registry import TASK_MAP
from collector.runtime.runner import run_task


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(description="AI Invest Assistant Collector")
    parser.add_argument("task", choices=TASK_MAP.keys(), help="采集任务名称")
    parser.add_argument("--period", default="daily", help="K 线周期")
    parser.add_argument("--preferred-source", default=None, help="优先使用的渠道 source")
    parser.add_argument(
        "--symbols",
        default=None,
        help="股票代码列表，逗号分隔，用于 K 线/分钟线等任务",
    )
    parser.add_argument("--start-date", default=None, help="开始日期 (YYYY-MM-DD)")
    parser.add_argument("--end-date", default=None, help="结束日期 (YYYY-MM-DD)")
    parser.add_argument("--sector-type", default="industry", help="板块类型")
    parser.add_argument(
        "--report-date",
        default=None,
        help="财报发布日期 (YYYYMMDD)，用于基金持仓任务",
    )
    parser.add_argument(
        "--report-types",
        default=None,
        help="财报类型，逗号分隔，如 年报,半年报,一季报,三季报",
    )
    parser.add_argument(
        "--trade-date",
        default=None,
        help="交易日期 (YYYY-MM-DD)，用于涨停股池任务",
    )
    parser.add_argument(
        "--indicators",
        default=None,
        help="宏观经济指标，逗号分隔，如 cpi,pmi,gdp",
    )
    args = parser.parse_args()

    params: dict = {
        "task": args.task,
        "period": args.period,
        "preferred_source": args.preferred_source,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "sector_type": args.sector_type,
        "report_date": args.report_date,
        "trade_date": args.trade_date,
    }
    if args.report_types:
        params["report_types"] = args.report_types.split(",")
    if args.indicators:
        params["indicators"] = args.indicators.split(",")
    if args.symbols:
        params["symbols"] = args.symbols.split(",")

    result = asyncio.run(run_task(params))
    if result.status.value == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
