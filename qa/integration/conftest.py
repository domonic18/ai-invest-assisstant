"""端到端测试共享 fixtures — 黑盒访问运行中的 Docker 栈。

环境变量：
- QA_BASE_URL: 被测栈入口，默认 http://localhost:9000（web 容器 nginx）
- QA_ADMIN_USERNAME / QA_ADMIN_PASSWORD: 管理员账号，默认 qa_admin；
  全新部署时该账号会自动注册为首个用户（首个注册用户即 admin）。
  若数据库已有其他用户，需保证该账号已存在且为 admin，否则管理端用例跳过。
"""

import os
import time
from typing import Any

import httpx
import pytest

BASE_URL = os.getenv("QA_BASE_URL", "http://localhost:9000")
API_V1 = f"{BASE_URL}/api/v1"
ADMIN_USERNAME = os.getenv("QA_ADMIN_USERNAME", "qa_admin")
ADMIN_PASSWORD = os.getenv("QA_ADMIN_PASSWORD", "qa_admin_pass_123")
ADMIN_EMAIL = f"{ADMIN_USERNAME}@qa.example.com"

TERMINAL_STATUSES = {"success", "partial", "failed", "skipped"}


@pytest.fixture(scope="session")
def client() -> httpx.Client:
    """指向被测栈的 HTTP 客户端。"""
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as http_client:
        yield http_client


@pytest.fixture(scope="session")
def admin_token(client: httpx.Client) -> str:
    """登录（必要时先注册）QA 管理员账号，返回 JWT。"""
    token = _login(client)
    if token is None:
        _register(client)
        token = _login(client)
    if token is None:
        pytest.fail(f"无法登录 QA 账号 {ADMIN_USERNAME}")

    probe = client.get(
        f"{API_V1}/admin/collector/logs",
        params={"limit": 1},
        headers=_auth_headers(token),
    )
    if probe.status_code == 403:
        pytest.skip(
            f"QA 账号 {ADMIN_USERNAME} 不是 admin；"
            "请在全新数据库上运行（首个注册用户自动成为 admin），"
            "或用 QA_ADMIN_USERNAME/QA_ADMIN_PASSWORD 指定已有管理员"
        )
    probe.raise_for_status()
    return token


def _login(client: httpx.Client) -> str | None:
    response = client.post(
        f"{API_V1}/auth/login",
        data={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
    if response.status_code == 401:
        return None
    response.raise_for_status()
    return str(response.json()["access_token"])


def _register(client: httpx.Client) -> None:
    response = client.post(
        f"{API_V1}/auth/register",
        json={
            "username": ADMIN_USERNAME,
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
        },
    )
    if response.status_code in (200, 201, 400, 409):
        return
    response.raise_for_status()


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def admin_client(client: httpx.Client, admin_token: str) -> httpx.Client:
    """携带 admin JWT 的客户端（共享底层连接）。"""
    client.headers.update(_auth_headers(admin_token))
    return client


def run_task_and_wait(
    client: httpx.Client,
    task_name: str,
    params: dict[str, Any] | None = None,
    timeout: float = 180.0,
    interval: float = 3.0,
) -> dict[str, Any]:
    """触发采集任务并轮询 collector_log 直到终态，返回日志条目。"""
    response = client.post(
        f"{API_V1}/admin/collector/tasks/{task_name}/run",
        json=params or {},
    )
    assert response.status_code == 200, f"dispatch {task_name} 失败: {response.text}"
    log_id = response.json()["log_id"]

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        logs = client.get(
            f"{API_V1}/admin/collector/logs", params={"limit": 100}
        ).json()
        entry = next((log for log in logs if log["id"] == log_id), None)
        if entry and entry["status"] in TERMINAL_STATUSES:
            return entry
        time.sleep(interval)

    pytest.fail(f"任务 {task_name} (log_id={log_id}) 在 {timeout}s 内未完成")
    raise AssertionError("unreachable")
