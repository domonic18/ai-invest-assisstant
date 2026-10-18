"""功能模块目录：用户组权限的可配置 key 集合。

路由级门控（require_feature）与前端菜单/路由守卫共用此清单；
不在目录内的路由（工作台、行情、个股等核心浏览功能）对所有用户开放。
"""

FEATURE_KEYS: list[str] = [
    "kb",
    "assistant",
    "screening",
    "research",
    "financial-reports",
    "paper-trade",
    "skills",
    "news",
    "chain",
    "anomaly",
    "auction",
    "fund-flow",
]

FEATURE_LABELS: dict[str, str] = {
    "kb": "知识库查询",
    "assistant": "AI 助手",
    "screening": "AI 选股",
    "research": "AI 研报",
    "financial-reports": "AI 财报解读",
    "paper-trade": "模拟交易",
    "skills": "技能广场",
    "news": "资讯中心",
    "chain": "产业图谱",
    "anomaly": "异动监测",
    "auction": "集合竞价",
    "fund-flow": "资金流向",
}
