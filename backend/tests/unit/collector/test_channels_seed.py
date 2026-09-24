"""渠道种子回填契约测试：base_url 仅补空不覆盖非空、幂等。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from collector.runtime.channels import DEFAULT_CHANNELS, seed_default_channels


def _row(source: str, base_url: str | None, types: list[str] | None = None):
    return SimpleNamespace(
        id=1,
        source=source,
        base_url=base_url,
        supported_data_types=types or [],
    )


def _session(execute_results: list[list[SimpleNamespace]]) -> AsyncMock:
    session = AsyncMock()
    results = []
    for rows in execute_results:
        result = MagicMock()
        result.scalars.return_value.all.return_value = rows
        results.append(result)
    session.execute = AsyncMock(side_effect=results)
    return session


@pytest.mark.unit
class TestSeedDefaultChannels:
    async def test_backfills_null_base_url_from_seed(self):
        row = _row("cls", None, ["cls-telegraph-backfill"])
        # executes: ① 渠道表 ② associations 渠道表 ③ 已有关联键
        session = _session([[row], [row], []])

        await seed_default_channels(session)

        assert row.base_url == "https://www.cls.cn"

    async def test_preserves_custom_base_url(self):
        row = _row("cls", "https://mirror.example.com", ["cls-telegraph-backfill"])
        session = _session([[row], [row], []])

        await seed_default_channels(session)

        assert row.base_url == "https://mirror.example.com"

    async def test_null_stays_null_when_seed_has_no_url(self):
        row = _row("eastmoney", None, ["fund-flow"])
        session = _session([[row], [row], []])

        await seed_default_channels(session)

        assert row.base_url is None

    async def test_no_changes_commit_skipped(self):
        # 全部默认渠道已存在且与种子一致 → 幂等零提交
        rows = [
            _row(
                data["source"],
                data.get("base_url"),
                sorted(data.get("supported_data_types", [])),
            )
            for data in DEFAULT_CHANNELS
        ]
        # associations 阶段渠道查不到（返回空）→ 无新增关联，全程零提交
        session = _session([rows, [], []])

        await seed_default_channels(session)

        session.commit.assert_not_awaited()
