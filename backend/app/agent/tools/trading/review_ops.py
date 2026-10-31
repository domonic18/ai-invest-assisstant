"""交易 Agent 复盘生成工具（B4）：对话内按需生成六档周期复盘。

与页面入口（``POST /admin/trading-agent/{agent_key}/review/generate``）落到
同一个 service 入口：页面走 Celery 异步派发（分钟级 LLM 不能阻塞 HTTP），
对话路径在工具内 await，完成后回写 ``paper_trading_review.complete`` 事件。
锁与缓存幂等完全复用 ``generate_review``。
"""

from datetime import date
from typing import Any, Literal

from langchain_core.tools import BaseTool, tool

from app.agent.tools.page_event import page_event
from app.core.database import AsyncSessionLocal

ReviewPeriodArg = Literal["day", "week", "month", "quarter", "half_year", "year"]


def make_generate_review_tool(agent_key: str) -> BaseTool:
    """构建复盘生成工具（闭包绑定 agent_key）。"""

    @tool
    async def generate_trading_review(
        period: ReviewPeriodArg | None = None,
        trade_date: str | None = None,
        scope: Literal["current", "previous"] = "current",
        start_date: str | None = None,
        end_date: str | None = None,
        regenerate: bool = False,
    ) -> dict[str, Any]:
        """生成交易 Agent 模拟盘的 AI 分层复盘（同步等待生成完成，分钟级）。

        已生成的同窗口复盘默认直接返回缓存；用户明确要求重做时才传
        regenerate=True。日/周/月另有盘后定时生成，季/半年/年只能经本工具
        或页面按需生成。

        Args:
            period: "day" 日度 / "week" 周度 / "month" 月度 / "quarter" 季度 /
                "half_year" 半年度 / "year" 年度。仅给 start_date/end_date 时可省略，
                由系统按区间跨度选择报告框架。缺省（无区间）按日度。
            trade_date: 基准交易日 YYYY-MM-DD，缺省取最新交易日。
            scope: "current" 本期（周期至今）/ "previous" 上一完整周期。
            start_date/end_date: 自定义区间 YYYY-MM-DD（须成对，映射到同一报告契约）。
            regenerate: 是否绕过缓存强制重新生成。

        Returns:
            period / trade_date / cached / overall / bias / suggestion /
            sections（key+title 清单）/ trades_count / experiences_count /
            no_target_reason。空仓无复盘对象时 no_target_reason 非空。
        """
        from app.core.exceptions import AppError
        from app.services.trading import agent_registry, agent_review_service

        def _parse(raw: str | None, name: str) -> tuple[date | None, dict[str, Any] | None]:
            if not raw:
                return None, None
            try:
                return date.fromisoformat(raw), None
            except ValueError:
                return None, {"error": f"无效的 {name}：{raw}（应为 YYYY-MM-DD）"}

        parsed_date, date_error = _parse(trade_date, "trade_date")
        if date_error:
            return date_error
        parsed_start, start_error = _parse(start_date, "start_date")
        if start_error:
            return start_error
        parsed_end, end_error = _parse(end_date, "end_date")
        if end_error:
            return end_error
        if (parsed_start is None) != (parsed_end is None):
            return {"error": "自定义区间须同时提供 start_date 与 end_date"}
        resolved_period = period or (
            None if parsed_start is not None else "day"
        )

        async with AsyncSessionLocal() as session:
            try:
                agent = await agent_registry.get_agent(session, agent_key)
                request = agent_review_service.ReviewWindowRequest.from_values(
                    period=resolved_period,
                    trade_date=parsed_date,
                    scope=scope,
                    start_date=parsed_start,
                    end_date=parsed_end,
                )
                result = await agent_review_service.generate_review(
                    session,
                    agent,
                    request,
                    regenerate=regenerate,
                    trigger="manual",
                )
            except AppError as exc:
                return {"error": str(exc)}

        content = result.content
        return {
            "period": content.period,
            "trade_date": content.trade_date,
            "cached": result.cached,
            "overall": content.overall,
            "bias": content.bias,
            "suggestion": content.suggestion,
            "sections": [
                {"key": s.key, "title": s.title} for s in content.sections
            ],
            "trades_count": len(content.trades),
            "experiences_count": len(content.experiences),
            "no_target_reason": content.no_target_reason,
            "__event__": page_event(
                "paper_trading_review.complete",
                agent_key=agent_key,
                period=content.period,
                trade_date=content.trade_date,
                regenerate=regenerate,
                cached=result.cached,
            ),
        }

    return generate_trading_review
