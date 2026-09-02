"""财联社接口签名与 sv 提取。

2026-09 探针实测结论（批次 A 调研回填）：cls 站点已迁 Next.js，旧
``nodeapi/telegraphList``/``api/cache`` 均失效，真实端点
``GET https://www.cls.cn/v1/roll/get_roll_list``。签名规则为
``md5_hex(sha1_hex(参数按 key 升序 k=v& 拼接))``（非社区旧版 k1v1k2v2
裸拼接）；sv（客户端版本号）硬编码于 ``_app`` bundle，可正则提取，
提取失败时回退到实测可用常量。
"""

import hashlib
import re
from typing import Any

#: sv 回退常量：_app bundle 提取失败时使用（探针实测可用）。
DEFAULT_SV = "8.7.9"

_SV_PATTERN = re.compile(r'sv[=:]"(\d+(?:\.\d+)+)"')


def build_cls_sign(params: dict[str, Any]) -> str:
    """按探针验证的规则生成 cls 接口签名。

    Args:
        params: 请求参数（值会被转为字符串）。

    Returns:
        ``md5(sha1_hex(sorted "k=v" joined by "&"))`` 的 32 位小写十六进制。
    """
    query = "&".join(f"{key}={params[key]}" for key in sorted(params))
    sha1_hex = hashlib.sha1(query.encode("utf-8")).hexdigest()
    return hashlib.md5(sha1_hex.encode("utf-8")).hexdigest()


def extract_sv(html: str) -> str:
    """从 cls 页面/_app bundle 的 HTML 中提取 sv 版本号，失败返回默认值。"""
    match = _SV_PATTERN.search(html)
    return match.group(1) if match else DEFAULT_SV
