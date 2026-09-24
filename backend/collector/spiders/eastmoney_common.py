"""东财渠道可替换 host 解析（WAF 镜像切换走渠道 extra 配置）。

push2 系 host 曾被 WAF 按 TLS 指纹+频控封禁，实时类端点已默认切
push2delay 镜像；运营侧可在渠道 ``extra`` 配 ``push2_base_url`` 整体
替换，无需改代码发版。历史 K 线 push2his 无公开镜像，保持常量。
"""

from typing import Any

PUSH2_BASE_URL_KEY = "push2_base_url"
DEFAULT_PUSH2_BASE_URL = "https://push2delay.eastmoney.com"


def push2_base_url(config: dict[str, Any]) -> str:
    """渠道 extra 的 ``push2_base_url`` 优先（非法值忽略），默认镜像 host。"""
    value = config.get(PUSH2_BASE_URL_KEY)
    if isinstance(value, str) and value.startswith("http"):
        return value.rstrip("/")
    return DEFAULT_PUSH2_BASE_URL
