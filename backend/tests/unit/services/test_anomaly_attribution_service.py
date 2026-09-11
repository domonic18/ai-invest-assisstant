"""异动 AI 归因服务单测（mock 仓储与 LLM 执行器，不触网不连库）。"""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.market import anomaly_attribution_service as svc
from app.services.market.anomaly_attribution_service import (
    StockAnomalyAttributionContent,
    StockAttributionItem,
)
from app.services.market.anomaly_common import AnomalyInputNotReadyError

_TRADE_DATE = date(2026, 9, 10)


def _stock_row(code: str, strength: int, rule: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        stock_code=code,
        stock_name=f"股票{code}",
        change_pct=7.5,
        turnover_rate=9.0,
        volume_ratio=3.0,
        is_above_ma60=True,
        ma60_breakout=rule == "breakout",
        anomaly_types=["volume"],
        strength=strength,
        attribution_category=rule,
        attribution_summary=None,
    )


def _session() -> AsyncMock:
    session = AsyncMock()
    return session


def _lock(acquired: bool):
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=acquired)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=ctx)


def _content(*codes: str, category: str = "breakout") -> StockAnomalyAttributionContent:
    return StockAnomalyAttributionContent(
        items=[
            StockAttributionItem(stock_code=code, category=category, summary=f"{code} 放量突破")
            for code in codes
        ]
    )


@pytest.mark.unit
class TestRunTopNAttribution:
    @pytest.mark.asyncio
    async def test_empty_rows_returns_zeros(self) -> None:
        session = _session()
        with patch.object(
            svc.anomaly_repository, "list_stock_anomalies", AsyncMock(return_value=[])
        ):
            stats = await svc.run_top_n_attribution(
                session, "stock", _TRADE_DATE, top_n=20
            )
        assert stats == {"targets": 0, "from_cache": 0, "generated": 0}
        session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_cache_hit_skips_llm_and_applies_entries(self) -> None:
        rows = [_stock_row("000001", 90, "acceleration"), _stock_row("600519", 80, "breakout")]
        session = _session()
        with (
            patch.object(
                svc.anomaly_repository,
                "list_stock_anomalies",
                AsyncMock(return_value=rows),
            ),
            patch.object(
                svc.ai_analysis_repository,
                "load_latest_success",
                AsyncMock(
                    side_effect=lambda session, skill_id, input_hash: SimpleNamespace(
                        structured_output={"category": "breakout", "summary": "资金抢筹"}
                    )
                ),
            ),
        ):
            stats = await svc.run_top_n_attribution(session, "stock", _TRADE_DATE, top_n=20)

        assert stats == {"targets": 2, "from_cache": 2, "generated": 0}
        assert rows[0].attribution_category == "breakout"
        assert rows[0].attribution_summary == "资金抢筹"
        assert rows[1].attribution_category == "breakout"
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_pending_batch_single_llm_call_with_fallback(self) -> None:
        """未缓存标的合并一次 LLM 调用；漏标回退规则分类，非法分类被剔除。"""
        rows = [
            _stock_row("000001", 90, "acceleration"),
            _stock_row("600519", 80, "breakout"),
            _stock_row("300750", 70, "pullback"),
        ]
        session = _session()
        insert = AsyncMock()
        with (
            patch.object(
                svc.anomaly_repository,
                "list_stock_anomalies",
                AsyncMock(return_value=rows),
            ),
            patch.object(
                svc.ai_analysis_repository,
                "load_latest_success",
                AsyncMock(return_value=None),
            ),
            patch.object(svc.ai_analysis_repository, "insert_result", insert),
            patch.object(svc, "redis_lock", _lock(True)),
            patch(
                "app.agent.skills.anomaly_attribution_agent.run_skill",
                AsyncMock(
                    return_value=(
                        _content("000001", "600519", category="acceleration"),
                        "openai/gpt",
                        1234,
                    )
                ),
            ) as mock_run,
        ):
            stats = await svc.run_top_n_attribution(session, "stock", _TRADE_DATE, top_n=20)

        assert stats["targets"] == 3
        assert stats["from_cache"] == 0
        assert stats["generated"] == 3
        mock_run.assert_awaited_once()
        # 300750 未在 LLM 输出中：回退规则分类 + 占位摘要
        assert rows[2].attribution_category == "pullback"
        assert rows[2].attribution_summary == "证据不足，保留规则分类"
        assert rows[0].attribution_category == "acceleration"
        # 3 条底稿 + commit
        assert insert.await_count == 3
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_lock_not_acquired_skips_generation(self) -> None:
        rows = [_stock_row("000001", 90, "acceleration")]
        session = _session()
        with (
            patch.object(
                svc.anomaly_repository,
                "list_stock_anomalies",
                AsyncMock(return_value=rows),
            ),
            patch.object(
                svc.ai_analysis_repository,
                "load_latest_success",
                AsyncMock(return_value=None),
            ),
            patch.object(svc, "redis_lock", _lock(False)),
        ):
            stats = await svc.run_top_n_attribution(session, "stock", _TRADE_DATE, top_n=20)

        assert stats["generated"] == 0
        # 未生成不落库：保持规则分类原状，但缓存复用/跳过不阻断回写
        session.commit.assert_awaited_once()


@pytest.mark.unit
class TestPersistManualAttribution:
    @pytest.mark.asyncio
    async def test_no_rows_raises_not_ready(self) -> None:
        session = _session()
        with patch.object(
            svc.anomaly_repository, "list_stock_anomalies", AsyncMock(return_value=[])
        ):
            with pytest.raises(AnomalyInputNotReadyError):
                await svc.persist_manual_attribution(
                    session,
                    "stock",
                    _TRADE_DATE,
                    [{"stock_code": "000001", "category": "breakout", "summary": "x"}],
                    model="openai/gpt",
                )

    @pytest.mark.asyncio
    async def test_valid_entries_update_rows_and_cache(self) -> None:
        rows = [_stock_row("000001", 90), _stock_row("600519", 80)]
        session = _session()
        insert = AsyncMock()
        with patch.object(
            svc.anomaly_repository,
            "list_stock_anomalies",
            AsyncMock(return_value=rows),
        ), patch.object(svc.ai_analysis_repository, "insert_result", insert):
            result = await svc.persist_manual_attribution(
                session,
                "stock",
                _TRADE_DATE,
                [
                    {"stock_code": "000001", "category": "breakout", "summary": "突破"},
                    {"stock_code": "999999", "category": "breakout", "summary": "清单外"},
                    {"stock_code": "600519", "category": "no-such", "summary": "非法分类"},
                ],
                model="openai/gpt",
            )

        assert result == {"attributed": 1, "skipped": 2}
        assert rows[0].attribution_category == "breakout"
        assert rows[0].attribution_summary == "突破"
        assert rows[1].attribution_category is None
        insert.assert_awaited_once()
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_all_invalid_raises_value_error(self) -> None:
        rows = [_stock_row("000001", 90)]
        session = _session()
        with patch.object(
            svc.anomaly_repository,
            "list_stock_anomalies",
            AsyncMock(return_value=rows),
        ):
            with pytest.raises(ValueError):
                await svc.persist_manual_attribution(
                    session,
                    "stock",
                    _TRADE_DATE,
                    [{"stock_code": "999999", "category": "breakout", "summary": "x"}],
                    model="openai/gpt",
                )


@pytest.mark.unit
class TestInputHash:
    def test_hash_binds_domain_code_and_date(self) -> None:
        h1 = svc._input_hash("stock", "000001", _TRADE_DATE)
        h2 = svc._input_hash("stock", "000001", _TRADE_DATE)
        h3 = svc._input_hash("stock", "000001", date(2026, 9, 9))
        h4 = svc._input_hash("sector", "000001", _TRADE_DATE)
        assert h1 == h2
        assert h1 != h3
        assert h1 != h4
