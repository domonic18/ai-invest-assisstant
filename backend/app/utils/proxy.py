"""代理 URL 组装工具。

管理端测试与采集运行时共用：把 proxy_config 的结构化字段组装为
requests / curl_cffi 可直接使用的 ``proxies`` 目标 URL。
"""

from urllib.parse import quote


def build_proxy_url(
    protocol: str,
    host: str,
    port: int,
    username: str | None = None,
    password: str | None = None,
) -> str:
    """组装代理 URL，如 ``http://user:pass@host:port``。

    凭据按 RFC 3986 百分号编码（``@`` ``:`` 等特殊字符不破坏 URL 结构）；
    仅用户名无密码时密码段为空。
    """
    if username:
        credentials = quote(username, safe="")
        if password:
            credentials += f":{quote(password, safe='')}"
        return f"{protocol}://{credentials}@{host}:{port}"
    return f"{protocol}://{host}:{port}"
