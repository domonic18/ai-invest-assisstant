"""采集错误归因分类器（纯函数，有序正则短路）。

从 ``collector_log.error_msg`` 原文提取错误归因分类，供健康快照的
``last_error_cause`` 列与渠道视图的归因分布使用。规则顺序即优先级：
最特异的信号在前，未命中任何规则时兜底 ``other``。模式来自本地库
30 天实证错误样本（东财 push2 WAF、新浪反爬 HTML、连接超时等）。
"""

import re

CAUSE_WAF = "waf"
CAUSE_NETWORK = "network"
CAUSE_PARSE = "parse"
CAUSE_AUTH = "auth"
CAUSE_TIMEOUT = "timeout"
CAUSE_NOT_READY = "not_ready"
CAUSE_OTHER = "other"

CAUSE_LABELS: dict[str, str] = {
    CAUSE_WAF: "WAF/反爬",
    CAUSE_NETWORK: "网络/超时",
    CAUSE_PARSE: "接口/解析",
    CAUSE_AUTH: "认证/配额",
    CAUSE_TIMEOUT: "任务超时",
    CAUSE_NOT_READY: "输入未就绪",
    CAUSE_OTHER: "其他",
}

# 有序规则：元组顺序即判定优先级
_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    # 任务执行超时（SoftTimeLimitExceeded 由 runner 记录）
    (CAUSE_TIMEOUT, re.compile(r"SoftTimeLimitExceeded|TimeLimitExceeded|执行超时", re.I)),
    # 输入数据未就绪（ReviewInputDataNotReadyError / kline-freshness 缺口）
    (CAUSE_NOT_READY, re.compile(r"NotReady|未就绪|仍缺日 ?K")),
    # 认证与配额
    (
        CAUSE_AUTH,
        re.compile(r"401|Unauthorized|API[ _-]?key|quota|配额|认证失败|签名错误|token 过期", re.I),
    ),
    # WAF/反爬：403、反爬页导致的 HTML 解析失败、东财 push2 主机连败
    (
        CAUSE_WAF,
        re.compile(
            r"403|Forbidden|WAF|反爬|anti-?crawl"
            r"|Can not decode value starting with character '<'"
            r"|No value to decode"
            r"|Expecting value: line 1 column 1"
            r"|decode value starting with character '<'",
            re.I,
        ),
    ),
    # 东财主机 + Max retries 组合判 WAF（拦截按主机指纹，连接层表现为重试耗尽）
    (
        CAUSE_WAF,
        re.compile(
            r"(push2|eastmoney)[^\n]{0,200}Max retries"
            r"|Max retries[^\n]{0,200}(push2|eastmoney)",
            re.I,
        ),
    ),
    # 接口变更/解析失败
    (
        CAUSE_PARSE,
        re.compile(
            r"JSONDecodeError|KeyError|ParseError|解析失败|ValueError"
            r"|IndexError|AttributeError|字段.{0,8}不存在|不存在.{0,8}字段",
            re.I,
        ),
    ),
    # 网络层：连接超时/重置/DNS/SSL
    (
        CAUSE_NETWORK,
        re.compile(
            r"Max retries exceeded|Connection aborted|RemoteDisconnected"
            r"|ConnectionReset|Connection refused|Timed?[ _]?out|timeout"
            r"|getaddrinfo failed|Name or service not known"
            r"|Unknown identifier|Network is unreachable|SSLError"
            r"|Failed to resolve|Connection broken",
            re.I,
        ),
    ),
)


def classify_error(error_msg: str | None) -> str:
    """把错误原文归因为 7 类之一；空文本返回 ``other``。

    Args:
        error_msg: ``collector_log.error_msg`` 原文，可为空。

    Returns:
        归因分类常量（waf/network/parse/auth/timeout/not_ready/other）。
    """
    if not error_msg:
        return CAUSE_OTHER
    for cause, pattern in _RULES:
        if pattern.search(error_msg):
            return cause
    return CAUSE_OTHER
