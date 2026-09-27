"""unit 测试密闭性守卫。

recorder（agent_run_recorder）为观测解耦刻意绕过业务事务、自开
AsyncSessionLocal 写库——宿主机本地库可达时会绕过测试 mock 真实写入
（2026-09-27 实测 unit 套件在本地库落了 failed 轨迹行）。autouse 把
recorder 的会话工厂替换为必抛替身，走其「无库静默降级」路径即单测约定；
recorder 自身契约测试可在用例内再次 patch 覆盖本守卫。
"""

import pytest


@pytest.fixture(autouse=True)
def _recorder_offline(monkeypatch):
    def _boom(*args, **kwargs):
        raise RuntimeError("unit tests must not touch a real database")

    monkeypatch.setattr(
        "app.services.trading.agent_run_recorder.AsyncSessionLocal", _boom
    )
