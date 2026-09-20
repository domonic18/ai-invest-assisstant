"""模型服务 base_url 归一化（单一真相源）。

用户常从厂商文档直接粘贴完整端点（如 ``…/v4/embeddings``），而各客户端
约定持有 API 根地址后自行拼接路径（行业通行做法：先剥尾斜杠与已知端点
后缀，根地址原样保留）。所有直连 HTTP 的模型客户端与连通性测试统一经
此归一化，禁止各自手写 ``rstrip("/")``。
"""

_ENDPOINT_SUFFIXES = (
    "/chat/completions",
    "/embeddings",
    "/speech_to_text",
    "/v1/messages",
)


def normalize_api_base(base_url: str) -> str:
    """剥离首尾空白、尾斜杠与已知端点后缀，返回 API 根地址。

    Examples:
        ``…/v4/embeddings`` → ``…/v4``；``…/v1/chat/completions`` → ``…/v1``；
        ``…/v1`` 与裸域名原样保留。
    """
    base = (base_url or "").strip().rstrip("/")
    for suffix in _ENDPOINT_SUFFIXES:
        if base.endswith(suffix):
            return base[: -len(suffix)].rstrip("/")
    return base


def normalize_asr_base(base_url: str) -> str:
    """ASR 通道专用：客户端自拼 ``/v1/speech_to_text``，根地址不含版本段。"""
    base = normalize_api_base(base_url)
    if base.endswith("/v1"):
        return base[: -len("/v1")].rstrip("/")
    return base
