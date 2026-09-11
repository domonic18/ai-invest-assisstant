"""异动检测域共享原语：输入未就绪异常与命中维度/分类键。

维度键落 ``anomaly_types`` JSONB、分类键落 ``attribution_category``，
前端标签映射在 ``shared/types``（docs/arch/08-anomaly-analysis.md §2-§4）。
"""

from app.core.exceptions import BadRequestError

# 板块命中维度
SECTOR_DIM_PRICE = "price"
SECTOR_DIM_VOLUME = "volume"
SECTOR_DIM_SYNC = "sync"

# 个股命中维度
STOCK_DIM_MA60_BREAKOUT = "ma60_breakout"
STOCK_DIM_VOLUME = "volume"
STOCK_DIM_TURNOVER = "turnover"
STOCK_DIM_PRICE = "price"

# 分类（检测阶段按规则落值，归因阶段可被 LLM 覆盖）
CATEGORY_RESONANCE = "resonance"
CATEGORY_ROTATION = "rotation"
CATEGORY_BREAKOUT = "breakout"
CATEGORY_ACCELERATION = "acceleration"
CATEGORY_PULLBACK = "pullback"


class AnomalyInputNotReadyError(BadRequestError):
    """异动检测输入（板块快照 / 全市场快照）尚未就绪，定时任务退避重试。"""

    default_message = "异动检测输入数据尚未就绪，请稍后重试"
