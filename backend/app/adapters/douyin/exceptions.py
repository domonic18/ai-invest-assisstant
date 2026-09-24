"""抖音适配层归因异常（F-MON 故障归因与重试策略依赖此分类，禁止合并为泛型错误）。

处置约定（见 docs/arch/11-social-sentiment.md）：
- SignatureError / StructureDriftError：签名过时或页面结构巨变，直接 FAILED 告警跟版；
- RiskControlError：cookie 失效/频控，jar 冷却换 jar 退避重试；
- AccountInvalidError：单个账号问题，记 last_error 不停用账号。
"""


class DouyinAdapterError(Exception):
    """适配层异常基类。"""


class SignatureError(DouyinAdapterError):
    """a_bogus 签名被服务端拒绝（算法过时，需跟版 signing.py）。"""


class RiskControlError(DouyinAdapterError):
    """命中风控（403/429/captcha/频控状态码），可冷却后重试。"""


class AccountInvalidError(DouyinAdapterError):
    """追踪账号不存在、注销或转私密。"""


class StructureDriftError(DouyinAdapterError):
    """响应顶层结构与预期不符（接口契约变化）。"""
