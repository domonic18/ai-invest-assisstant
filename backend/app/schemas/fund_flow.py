"""个股资金流向的 Pydantic schemas。"""

from datetime import date

from app.schemas.base import CamelModel


class FundFlowResponse(CamelModel):
    """个股资金流向响应。

    金额字段用 float 而非 Decimal：Pydantic v2 会把 Decimal 序列化成
    JSON 字符串，违背 shared 契约声明的 number 类型。
    """

    stock_code: str
    trade_date: date
    main_net_inflow: float | None = None
    super_large_net: float | None = None
    large_net: float | None = None
    medium_net: float | None = None
    small_net: float | None = None
