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
    "/audio/transcriptions",
    "/v1/messages",
    "/v1/systemone",
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
    """ASR 通道专用（MiniMax 协议）：客户端自拼 ``/v1/speech_to_text``，
    根地址不含版本段。"""
    base = normalize_api_base(base_url)
    if base.endswith("/v1"):
        return base[: -len("/v1")].rstrip("/")
    return base


def normalize_openai_asr_base(base_url: str) -> str:
    """OpenAI 兼容转写专用：客户端自拼 ``/audio/transcriptions``。

    裸主机地址补 ``/v1``（OpenAI 路径约定，适配本地部署如
    ``http://localhost:8080``）；带路径的地址原样保留——网关自定义挂载点
    由用户显式给出。
    """
    base = normalize_api_base(base_url)
    # scheme://host 之外无路径段（split 后 ≤3 段）即视为裸主机
    if len(base.split("/")) <= 3:
        return f"{base}/v1"
    return base
