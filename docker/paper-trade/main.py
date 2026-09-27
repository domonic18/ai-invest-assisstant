"""掘金线上仿真交易 REST 网关（sidecar，组织方式同 douyin-signer）。

gmtrade SDK 的云端 TCP 网关（api.myquant.cn:9000）已废弃（服务端拒绝连接，SDK 自
2023-10 停更），现行仿真柜台是 sim.myquant.cn 网页版同款 REST API：
  - 网关地址经 discovery.myquant.cn 服务发现（GET /v1/discovery/services?names=broker-rpcgw），
    可用 GMTRADE_BROKER_URL 钉死跳过发现；
  - 鉴权用仿真页 token 作 Bearer（即 gmtrade set_token 同一个 token）。
sidecar 无状态多租户：token 与 account_id 由调用方（app 服务层）经请求头
X-Gm-Token / X-Gm-Account-Id 逐请求传入（凭证只存 app 库，不落 sidecar 环境）。
symbol 用掘金代码格式（SHSE.600000 / SZSE.000001）；柜台侧报文原样透传。
通道门禁：PAPER_TRADE_SHARED_SECRET 非空时，业务请求须带同值 X-Shared-Secret
（/health 豁免；留空 = 不校验，仅限 compose 内网部署）。
"""

import hmac
import os
import threading
from dataclasses import dataclass
from typing import Annotated, Any, Literal

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

DISCOVERY_URL = "https://discovery.myquant.cn/v1/discovery/services"
CALL_TIMEOUT = float(os.environ.get("GMTRADE_CALL_TIMEOUT", "10"))
SHARED_SECRET_HEADER = "X-Shared-Secret"
_shared_secret = os.environ.get("PAPER_TRADE_SHARED_SECRET", "").strip()


async def _require_shared_secret(request: Request) -> None:
    """通道级门禁：防 sidecar 发布公网后无鉴权裸奔（业务鉴权仍是逐请求 GM token）。

    /health 豁免（容器健康探活）；密钥未配置 = 内网部署，不启用。
    """
    if not _shared_secret or request.url.path == "/health":
        return
    provided = request.headers.get(SHARED_SECRET_HEADER, "").encode("utf-8")
    if not hmac.compare_digest(provided, _shared_secret.encode("utf-8")):
        raise HTTPException(401, f"缺少或错误的 {SHARED_SECRET_HEADER} 请求头")


app = FastAPI(
    title="paper-trade gateway",
    docs_url=None,
    redoc_url=None,
    dependencies=[Depends(_require_shared_secret)],
)

_client: httpx.AsyncClient | None = None
_broker_base = os.environ.get("GMTRADE_BROKER_URL", "").strip().rstrip("/")
_lock = threading.Lock()


@dataclass(frozen=True)
class Credentials:
    """单次请求的柜台凭证（调用方逐请求携带，sidecar 不落库不缓存）。"""

    token: str
    account_id: str


def credentials(
    x_gm_token: Annotated[str | None, Header(alias="X-Gm-Token")] = None,
    x_gm_account_id: Annotated[str | None, Header(alias="X-Gm-Account-Id")] = None,
) -> Credentials:
    token = (x_gm_token or "").strip()
    account_id = (x_gm_account_id or "").strip()
    if not token or not account_id:
        raise HTTPException(400, "缺少 X-Gm-Token / X-Gm-Account-Id 请求头")
    return Credentials(token=token, account_id=account_id)


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                _client = httpx.AsyncClient(
                    timeout=httpx.Timeout(CALL_TIMEOUT, connect=5.0),
                )
    return _client


async def _resolve_broker(force: bool = False) -> str:
    """柜台地址：GMTRADE_BROKER_URL 钉死优先，否则 discovery 服务发现并缓存。"""
    global _broker_base
    if _broker_base and not force:
        return _broker_base
    with _lock:
        if _broker_base and not force:
            return _broker_base
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(CALL_TIMEOUT, connect=5.0)) as c:
                r = await c.get(DISCOVERY_URL, params=[("names", "broker-rpcgw")])
                r.raise_for_status()
                rec = (r.json().get("data") or {}).get("broker-rpcgw") or {}
                scheme = str(rec.get("scheme", "HTTP")).lower()
                addr = str(rec.get("address", "")).strip()
                port = str(rec.get("port", "")).strip()
                if not addr:
                    raise HTTPException(502, "discovery 未返回仿真柜台地址")
                # address 自带端口或 port 缺省时直接用 address，否则拼 port
                base = f"{scheme}://{addr}" if ":" in addr or port in ("", "0") else f"{scheme}://{addr}:{port}"
        except httpx.HTTPError as exc:
            raise HTTPException(502, f"discovery 服务发现失败: {exc}") from exc
        _broker_base = base
    return _broker_base


async def _broker_request(
    method: str,
    path: str,
    *,
    token: str,
    params: dict | None = None,
    json_body: Any = None,
    _retry: bool = True,
) -> Any:
    base = await _resolve_broker()
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = await _get_client().request(
            method, base + path, params=params, json=json_body, headers=headers
        )
    except httpx.TransportError:
        # 柜台地址会随服务方调度漂移，连接级失败强制重新服务发现再试一次
        if not _retry:
            raise HTTPException(502, "仿真柜台网络不可达")
        await _resolve_broker(force=True)
        return await _broker_request(
            method, path, token=token, params=params, json_body=json_body, _retry=False
        )
    if r.status_code == 401:
        raise HTTPException(503, "掘金仿真 token 无效（sim.myquant.cn 个人中心可重置）")
    if r.status_code >= 400:
        try:
            detail = r.json().get("error") or r.text
        except Exception:
            detail = r.text
        raise HTTPException(502, f"仿真柜台返回 {r.status_code}: {detail}")
    return r.json()


def _unwrap(body: Any) -> Any:
    """柜台统一 {"data": ...} 包裹；空结果可能是 {}，剥掉包裹还原业务数据。"""
    if isinstance(body, dict) and "data" in body:
        return body["data"]
    return body


@app.get("/health")
def health() -> dict:
    # 永远可答（同 douyin-signer 约定）；不探活掘金
    return {"status": "ok"}


@app.get("/cash")
async def cash(cred: Credentials = Depends(credentials)) -> Any:
    return _unwrap(await _broker_request("GET", f"/v3/account-trade/cash/{cred.account_id}", token=cred.token))


@app.get("/positions")
async def positions(cred: Credentials = Depends(credentials)) -> Any:
    return _unwrap(await _broker_request("GET", f"/v3/account-trade/positions/{cred.account_id}", token=cred.token))


@app.get("/orders")
async def orders(cred: Credentials = Depends(credentials)) -> Any:
    # 当日委托（盘中即可查）；orders/ 为历史委托需日期过滤，盘后同步走这里即可覆盖
    return _unwrap(await _broker_request("GET", f"/v3/account-trade/intraday-orders/{cred.account_id}", token=cred.token))


@app.get("/orders/unfinished")
async def unfinished_orders(cred: Credentials = Depends(credentials)) -> Any:
    return _unwrap(await _broker_request("GET", f"/v3/account-trade/unfinished-orders/{cred.account_id}", token=cred.token))


@app.get("/orders/executions")
async def execution_reports(cred: Credentials = Depends(credentials)) -> Any:
    return _unwrap(await _broker_request("GET", f"/v3/account-trade/intraday-execrpts/{cred.account_id}", token=cred.token))


class OrderIn(BaseModel):
    symbol: str = Field(description="掘金代码：SHSE.600000 / SZSE.000001")
    volume: int = Field(gt=0, description="股数，A股按手(100)整数倍由掘金校验")
    side: Literal["buy", "sell"]
    order_type: Literal["limit", "market"] = "limit"
    price: float = Field(default=0, ge=0)


_SIDE = {"buy": 1, "sell": 2}
_ORDER_TYPE = {"limit": 1, "market": 2}


@app.post("/orders")
async def place_order(req: OrderIn, cred: Credentials = Depends(credentials)) -> Any:
    if req.order_type == "limit" and req.price <= 0:
        raise HTTPException(422, "限价单必须带 price")
    resp = await _broker_request(
        "POST",
        "/v3/account-trade/orders",
        token=cred.token,
        json_body={
            "data": [
                {
                    "accountId": cred.account_id,
                    "symbol": req.symbol,
                    "side": _SIDE[req.side],
                    "orderType": _ORDER_TYPE[req.order_type],
                    # 股票现货：买开/卖平（网页端对非期货也是 side 直传 positionEffect）
                    "positionEffect": _SIDE[req.side],
                    "price": req.price,
                    "volume": req.volume,
                }
            ]
        },
    )
    data = _unwrap(resp)
    # 柜台拒单时 HTTP 仍 200，拒绝原因在委托对象上（柜台异步校验，此处只能拦同步拒单）
    row = data[0] if isinstance(data, list) and data and isinstance(data[0], dict) else None
    if row and row.get("ord_rej_reason"):
        raise HTTPException(502, f"委托被拒绝: {row.get('ord_rej_reason_detail') or row.get('ord_rej_reason')}")
    return data


@app.delete("/orders/{cl_ord_id}")
async def cancel_order(cl_ord_id: str, cred: Credentials = Depends(credentials)) -> Any:
    return _unwrap(
        await _broker_request(
            "POST",
            "/v3/account-trade/cancel-orders",
            token=cred.token,
            json_body={"data": [{"accountId": cred.account_id, "clOrdId": cl_ord_id}]},
        )
    )


@app.delete("/orders")
async def cancel_all_orders(cred: Credentials = Depends(credentials)) -> Any:
    return _unwrap(
        await _broker_request(
            "POST",
            "/v3/account-trade/cancel-all-orders",
            token=cred.token,
            json_body={"accountIds": [cred.account_id]},
        )
    )
