"""common/formatters 金额格式化契约测试。

两个格式化器是**有意的口径差异**（见模块 docstring）：此测试钉住各自输出，
防止未来被"统一"成单一实现导致某处展示口径静默漂移。
"""

import pytest

from app.services.common.formatters import format_amount, format_amount_yi


@pytest.mark.unit
class TestFormatAmount:
    def test_none_is_unknown(self) -> None:
        assert format_amount(None) == "未知"

    def test_trillion_tier_two_decimals(self) -> None:
        assert format_amount(2.66e12) == "2.66 万亿元"

    def test_exactly_one_trillion_uses_trillion_tier(self) -> None:
        assert format_amount(1e12) == "1.00 万亿元"

    def test_below_trillion_uses_yi_integer(self) -> None:
        assert format_amount(9.5e11) == "9500 亿元"


@pytest.mark.unit
class TestFormatAmountYi:
    def test_none_is_unknown(self) -> None:
        assert format_amount_yi(None) == "未知"

    def test_fixed_yi_one_decimal_even_for_trillion(self) -> None:
        # 与 format_amount 的关键差异：万亿量级仍按亿元展示
        assert format_amount_yi(2.66e12) == "26600.0 亿元"

    def test_one_decimal(self) -> None:
        assert format_amount_yi(9.5e9) == "95.0 亿元"


@pytest.mark.unit
class TestNormalizeIndustry:
    def test_strips_business_suffixes(self) -> None:
        from app.services.common.industry import normalize_industry

        assert normalize_industry("半导体产业链") == "半导体"
        assert normalize_industry("白酒行业") == "白酒"
        assert normalize_industry("光伏板块") == "光伏"
        assert normalize_industry(" 半导体 ") == "半导体"

    def test_plain_name_unchanged(self) -> None:
        from app.services.common.industry import normalize_industry

        assert normalize_industry("半导体") == "半导体"
