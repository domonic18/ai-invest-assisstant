"""TASK_TYPE_DOMAIN 与 TASK_SPECS 全键一致性（测试侧校验防漂移）。

constants.py 不 import collector.runtime（解环约定），覆盖关系在
测试侧钉死：注册表新增任务而域映射未跟时在此失败。
"""

import pytest

from app.core.constants import DOMAIN_AI, DOMAIN_KB, TASK_TYPE_DOMAIN
from collector.runtime.registry import TASK_SPECS

pytestmark = pytest.mark.unit

# 维护类任务自指豁免：监测不监测自己（health-check）、日志清理非数据域
MAINTENANCE_EXEMPT = {"health-check", "collector-log-cleanup"}


def test_task_type_domain_covers_all_specs():
    """TASK_SPECS 数据任务全键都有域归属（维护类自指豁免）。"""
    missing = sorted(set(TASK_SPECS) - set(TASK_TYPE_DOMAIN) - MAINTENANCE_EXEMPT)
    assert missing == [], f"TASK_TYPE_DOMAIN 缺少任务键: {missing}"


def test_task_type_domain_has_no_stale_keys():
    """域映射不含已下线的任务键。"""
    stale = sorted(set(TASK_TYPE_DOMAIN) - set(TASK_SPECS))
    assert stale == [], f"TASK_TYPE_DOMAIN 存在失效键: {stale}"


def test_health_check_self_exempt():
    """监测不监测自己：health-check 不在域映射中。"""
    assert "health-check" not in TASK_TYPE_DOMAIN


def test_domains_are_eight():
    """8 个数据域齐备（K线/行情/股池/资金流/资讯/基本面/AI/知识库）。"""
    assert set(TASK_TYPE_DOMAIN.values()) == {
        "kline", "quote", "pool", "fund-flow", "news", "fundamental", DOMAIN_AI,
        DOMAIN_KB,
    }


@pytest.mark.parametrize(
    "task_type",
    sorted(set(TASK_TYPE_DOMAIN)),
)
def test_domain_values_valid(task_type: str):
    assert TASK_TYPE_DOMAIN[task_type] in {
        "kline", "quote", "pool", "fund-flow", "news", "fundamental", DOMAIN_AI,
        DOMAIN_KB,
    }
