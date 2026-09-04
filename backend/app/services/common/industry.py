"""行业名称规范化（纯函数，无 IO）。"""


def normalize_industry(industry: str) -> str:
    """规范化行业名称，去除"产业链/行业/板块"业务后缀，保证前后端一致匹配。"""
    name = industry.strip()
    for suffix in ("产业链", "行业", "板块"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return name.strip()
