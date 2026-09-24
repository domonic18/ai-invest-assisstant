"""K 线画线域共享常量（schema 校验与 agent 工具层的单一来源）。"""

DRAWING_TARGET_TYPES = frozenset({"stock", "index", "sector"})
DRAWING_TYPES = frozenset({"trendline", "ray", "hline", "box", "text"})
DRAWING_DIRECTIONS = frozenset({"left", "right", "both"})
KLINE_DRAWING_PERIODS = frozenset({"daily", "weekly", "monthly"})

#: 画线类型 → 锚点数（hline 只有价格锚点，date 存空串）
REQUIRED_ANCHORS: dict[str, int] = {
    "trendline": 2,
    "ray": 2,
    "box": 2,
    "hline": 1,
    "text": 1,
}

#: AI 画线 label 上限（组内唯一键；工具层校验与 API 改名/采纳共用）
DRAWING_LABEL_MAX = 100

#: AI 画线单组条数上限（结构化输出体量与图层可读性约束）
AI_DRAWING_MAX_ITEMS = 20
