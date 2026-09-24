"""采集渠道调试服务契约测试：单渠道、只采集不落库、失败折叠。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1.admin.collector import get_collector_task_catalog
from app.schemas.collector import CollectorChannelDebugRequest
from app.services.admin.collector_debug import CollectorDebugService
from collector.runtime.registry import TASK_SPECS


def _config_mock(source: str = "sina", is_enabled: bool = True):
    config = MagicMock()
    config.id = 1
    config.source = source
    config.is_enabled = is_enabled
    return config


def _request(data_type: str = "etf-kline") -> CollectorChannelDebugRequest:
    return CollectorChannelDebugRequest(data_type=data_type)


def _service() -> CollectorDebugService:
    return CollectorDebugService(MagicMock())


@pytest.mark.unit
class TestCollectorDebugService:
    @pytest.mark.asyncio
    async def test_channel_not_found_folds_to_disabled(self) -> None:
        with patch(
            "app.repositories.base.BaseRepository.get", AsyncMock(return_value=None)
        ):
            result = await _service().debug_channel(999, _request())

        assert result.ok is False
        assert result.error_kind == "disabled"
        assert "不存在" in (result.error or "")

    @pytest.mark.asyncio
    async def test_disabled_channel_rejected(self) -> None:
        with patch(
            "app.repositories.base.BaseRepository.get",
            AsyncMock(return_value=_config_mock(is_enabled=False)),
        ):
            result = await _service().debug_channel(1, _request())

        assert result.ok is False
        assert result.error_kind == "disabled"
        assert "禁用" in (result.error or "")

    @pytest.mark.asyncio
    async def test_unknown_data_type_folds_to_no_collector(self) -> None:
        with patch(
            "app.repositories.base.BaseRepository.get",
            AsyncMock(return_value=_config_mock(source="sina")),
        ):
            result = await _service().debug_channel(1, _request("no-such-type"))

        assert result.ok is False
        assert result.error_kind == "no_collector"

    @pytest.mark.asyncio
    async def test_source_without_collector_folds_to_no_collector(self) -> None:
        # kline 任务仅声明 sina 渠道；eastmoney 应判定为无采集器
        with (
            patch(
                "app.repositories.base.BaseRepository.get",
                AsyncMock(return_value=_config_mock(source="eastmoney")),
            ),
            patch(
                "app.services.admin.collector_debug.resolve_collector_channel",
                AsyncMock(return_value={}),
            ),
        ):
            result = await _service().debug_channel(1, _request("kline"))

        assert result.ok is False
        assert result.error_kind == "no_collector"
        assert "kline" in (result.error or "")

    @pytest.mark.asyncio
    async def test_success_collects_without_store(self) -> None:
        raw_rows = [
            {"stock_code": "sh510300", "trade_date": "2026-07-20", "close": "4.0"},
            {"stock_code": "sh510300", "trade_date": "2026-07-21", "close": "4.1"},
            {"stock_code": "sh510300", "trade_date": "2026-07-22", "close": "4.2"},
            {"stock_code": "sh510300", "trade_date": "2026-07-23", "close": "4.3"},
        ]
        from collector.spiders.sina_etf_kline import SinaEtfKlineCollector

        with (
            patch(
                "app.repositories.base.BaseRepository.get",
                AsyncMock(return_value=_config_mock(source="sina")),
            ),
            patch(
                "app.services.admin.collector_debug.resolve_collector_channel",
                AsyncMock(
                    return_value={
                        "base_url": None,
                        "api_key": None,
                        "extra": {},
                        "proxy_url": None,
                    }
                ),
            ),
            patch.object(
                SinaEtfKlineCollector,
                "collect",
                AsyncMock(return_value=raw_rows),
            ) as mock_collect,
            patch.object(
                SinaEtfKlineCollector,
                "store",
                AsyncMock(),
            ) as mock_store,
        ):
            result = await _service().debug_channel(1, _request())

        assert result.ok is True
        assert result.error_kind is None
        assert result.collected == 4
        # 样例截断为前 3 条且全部通过 transform/validate
        assert result.sample_valid == 3
        assert len(result.sample_items) == 3
        assert result.sample_items[0]["stock_code"] == "sh510300"
        mock_collect.assert_awaited_once()
        mock_store.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_timeout_folds_with_kind(self) -> None:
        from collector.spiders.sina_etf_kline import SinaEtfKlineCollector

        async def slow_collect(self, **kwargs):  # noqa: ANN001
            import asyncio

            await asyncio.sleep(5)
            return []

        settings = MagicMock()
        settings.collector_debug_timeout_seconds = 0.01
        with (
            patch(
                "app.repositories.base.BaseRepository.get",
                AsyncMock(return_value=_config_mock(source="sina")),
            ),
            patch(
                "app.services.admin.collector_debug.resolve_collector_channel",
                AsyncMock(return_value={}),
            ),
            patch(
                "app.services.admin.collector_debug.get_settings",
                return_value=settings,
            ),
            patch.object(SinaEtfKlineCollector, "collect", slow_collect),
        ):
            result = await _service().debug_channel(1, _request())

        assert result.ok is False
        assert result.error_kind == "timeout"

    @pytest.mark.asyncio
    async def test_collect_exception_folds_to_error(self) -> None:
        from collector.spiders.sina_etf_kline import SinaEtfKlineCollector

        with (
            patch(
                "app.repositories.base.BaseRepository.get",
                AsyncMock(return_value=_config_mock(source="sina")),
            ),
            patch(
                "app.services.admin.collector_debug.resolve_collector_channel",
                AsyncMock(return_value={}),
            ),
            patch.object(
                SinaEtfKlineCollector,
                "collect",
                AsyncMock(side_effect=RuntimeError("新浪接口 502")),
            ),
        ):
            result = await _service().debug_channel(1, _request())

        assert result.ok is False
        assert result.error_kind == "error"
        assert "新浪接口 502" in (result.error or "")

    @pytest.mark.asyncio
    async def test_symbols_and_params_passed_to_collect(self) -> None:
        req = CollectorChannelDebugRequest(
            data_type="kline",
            symbols=["000001"],
            params={"period": "daily"},
        )
        # kline 的采集器为 sina_kline.SinaKlineCollector
        from collector.spiders.sina_kline import SinaKlineCollector

        with (
            patch(
                "app.repositories.base.BaseRepository.get",
                AsyncMock(return_value=_config_mock(source="sina")),
            ),
            patch(
                "app.services.admin.collector_debug.resolve_collector_channel",
                AsyncMock(return_value={}),
            ),
            patch.object(
                SinaKlineCollector,
                "collect",
                autospec=True,
            ) as mock_collect,
        ):
            mock_collect.return_value = []
            await _service().debug_channel(1, req)

        # config_params 进采集器构造 config（与 _run_collector_for_task 镜像一致）
        collector_self = mock_collect.await_args.args[0]
        assert collector_self.config["period"] == "daily"
        assert mock_collect.await_args.kwargs["symbols"] == ["000001"]


@pytest.mark.unit
class TestCollectorTaskCatalog:
    @pytest.mark.asyncio
    async def test_catalog_includes_defaults(self) -> None:
        response = await get_collector_task_catalog()
        by_name = {item.name: item for item in response.items}
        for name, spec in TASK_SPECS.items():
            item = by_name[name]
            assert item.defaults == dict(spec.defaults), name
            assert item.config_params == list(spec.config_params)
            assert item.run_params == list(spec.run_params)
