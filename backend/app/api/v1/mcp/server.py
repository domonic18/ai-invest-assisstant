"""平台 MCP Server（Streamable HTTP，多租户 API Key 鉴权）。

挂载于 ``/api/v1/mcp``（见 ``main.py``），FastMCP 内部路径 ``/mcp``：
客户端端点 ``https://<host>/api/v1/mcp``。单 uvicorn 进程 + stateless 模式，
``session_manager`` 由 FastAPI lifespan 托管（被挂载的子应用不会自动运行
自身 lifespan）。鉴权走 ``DbApiKeyVerifier`` → ``user_api_key`` 表。
"""

from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import AnyHttpUrl

from app.api.v1.mcp.tools import register_tools
from app.core.config import get_settings
from app.services.user.api_key_service import verify_api_key

#: FastMCP 内部路由路径；挂载层把精确外部路径重写为此路径
MCP_STREAMABLE_PATH = "/mcp"


class DbApiKeyVerifier(TokenVerifier):
    """静态 Bearer Token 校验（查 user_api_key，按 hash 命中）。"""

    async def verify_token(self, token: str) -> AccessToken | None:
        return await verify_api_key(token)


def _build_server() -> FastMCP:
    settings = get_settings()
    server = FastMCP(
        name="AI Invest Assistant",
        instructions=(
            "智能投研平台工具集：大盘复盘、板块/个股异动、散户情绪、"
            "交易 Agent 账户/计划/复盘/选股、知识库检索（只读），"
            "以及自选股分组与股票读写。交易下单/计划与 LLM 生成入口不开放；"
            "业务失败返回 {error: ...}；日期参数格式 YYYY-MM-DD，缺省取最新交易日。"
        ),
        token_verifier=DbApiKeyVerifier(),
        # 静态 Bearer 模式：issuer 仅作 AuthSettings 必填占位，不做 OAuth 发现
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(settings.mcp_issuer_url),
            resource_server_url=None,
        ),
        streamable_http_path=MCP_STREAMABLE_PATH,
        stateless_http=True,
        # 请求先经 Caddy 转发（Host 为公网域名），关闭 DNS rebinding 校验
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False
        ),
    )
    register_tools(server)
    return server


mcp_server = _build_server()
#: 供 FastAPI 挂载的 ASGI 应用（同时惰性创建 session_manager）
mcp_asgi_app = mcp_server.streamable_http_app()
