"""a_bogus 签名算法（自研移植，单点跟版）。

Ported from f2/utils/abogus.py (Apache-2.0 License) © Johnserf-Seed
https://github.com/Johnserf-Seed/f2 —— 保持算法行为逐字节等价，
SM3 以内联实现替代 gmssl 依赖（``_sm3.py``）。

抖音风控升级导致签名被拒（SignatureFailure）时，仅需对照上游更新本模块；
签名含时间戳与随机混淆，输出随调用变化属预期。
"""

from __future__ import annotations

import random
import time
from typing import Any

from app.adapters.douyin._sm3 import sm3_hash

SALT = "cus"
UA_KEY = b"\x00\x01\x0e"
AID = 6383
PAGE_ID = 0

ALPHABET_PRIMARY = "Dkdpgh2ZmsQB80/MfvV36XI1R45-WUAlEixNLwoqYTOPuzKFjJnry79HbGcaStCe"
ALPHABET_SECONDARY = "ckdp1h4ZKsUB80/Mfvw36XIgR25+WQAlEi7NLboqYTOPuzmFjJnryx9HVGDaStCe"

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0"
)

# GET 请求选项：14 兼容 8（POST 同款也可编码 params），统一写死 8 即可
OPTIONS_GET = [0, 1, 8]

_SORT_INDEX = [
    18, 20, 52, 26, 30, 34, 58, 38, 40, 53, 42, 21, 27, 54, 55, 31, 35, 57, 39,
    41, 43, 22, 28, 32, 60, 36, 23, 29, 33, 37, 44, 45, 59, 46, 47, 48, 49, 50,
    24, 25, 65, 66, 70, 71,
]
_SORT_INDEX_2 = [
    18, 20, 26, 30, 34, 38, 40, 42, 21, 27, 31, 35, 39, 41, 43, 22, 28, 32, 36,
    23, 29, 33, 37, 44, 45, 46, 47, 48, 49, 50, 24, 25, 52, 53, 54, 55, 57, 58,
    59, 60, 65, 66, 70, 71,
]

_BIG_ARRAY = [
    121, 243, 55, 234, 103, 36, 47, 228, 30, 231, 106, 6, 115, 95, 78, 101, 250,
    207, 198, 50, 139, 227, 220, 105, 97, 143, 34, 28, 194, 215, 18, 100, 159,
    160, 43, 8, 169, 217, 180, 120, 247, 45, 90, 11, 27, 197, 46, 3, 84, 72, 5,
    68, 62, 56, 221, 75, 144, 79, 73, 161, 178, 81, 64, 187, 134, 117, 186, 118,
    16, 241, 130, 71, 89, 147, 122, 129, 65, 40, 88, 150, 110, 219, 199, 255,
    181, 254, 48, 4, 195, 248, 208, 32, 116, 167, 69, 201, 17, 124, 125, 104,
    96, 83, 80, 127, 236, 108, 154, 126, 204, 15, 20, 135, 112, 158, 13, 1, 188,
    164, 210, 237, 222, 98, 212, 77, 253, 42, 170, 202, 26, 22, 29, 182, 251,
    10, 173, 152, 58, 138, 54, 141, 185, 33, 157, 31, 252, 132, 233, 235, 102,
    196, 191, 223, 240, 148, 39, 123, 92, 82, 128, 109, 57, 24, 38, 113, 209,
    245, 2, 119, 153, 229, 189, 214, 230, 174, 232, 63, 52, 205, 86, 140, 66,
    175, 111, 171, 246, 133, 238, 193, 99, 60, 74, 91, 225, 51, 76, 37, 145,
    211, 166, 151, 213, 206, 0, 200, 244, 176, 218, 44, 184, 172, 49, 216, 93,
    168, 53, 21, 183, 41, 67, 85, 224, 155, 226, 242, 87, 177, 146, 70, 190,
    12, 162, 19, 137, 114, 25, 165, 163, 192, 23, 59, 9, 94, 179, 107, 35, 7,
    142, 131, 239, 203, 149, 136, 61, 249, 14, 156,
]


def _js_shift_right(val: int, n: int) -> int:
    """JavaScript 无符号右移语义。"""
    return (val % 0x100000000) >> n


def _sm3_to_array(data: str | list[int]) -> list[int]:
    data_bytes = data.encode("utf-8") if isinstance(data, str) else bytes(data)
    hex_result = sm3_hash(data_bytes)
    return [int(hex_result[i : i + 2], 16) for i in range(0, len(hex_result), 2)]


def _rc4_encrypt(key: bytes, plaintext: str) -> bytes:
    s = list(range(256))
    j = 0
    for i in range(256):
        j = (j + s[i] + key[i % len(key)]) % 256
        s[i], s[j] = s[j], s[i]
    i = j = 0
    ciphertext: list[int] = []
    for char in plaintext:
        i = (i + 1) % 256
        j = (j + s[i]) % 256
        s[i], s[j] = s[j], s[i]
        ciphertext.append(ord(char) ^ s[(s[i] + s[j]) % 256])
    return bytes(ciphertext)


def _custom_b64_encode(input_string: str, alphabet: str) -> str:
    binary = "".join(f"{ord(char):08b}" for char in input_string)
    padding = (6 - len(binary) % 6) % 6
    binary += "0" * padding
    indices = [int(binary[i : i + 6], 2) for i in range(0, len(binary), 6)]
    output = "".join(alphabet[index] for index in indices)
    return output + "=" * (padding // 2)


def _abogus_encode(byte_str: str, alphabet: str) -> str:
    out: list[str] = []
    for i in range(0, len(byte_str), 3):
        if i + 2 < len(byte_str):
            n = (
                (ord(byte_str[i]) << 16)
                | (ord(byte_str[i + 1]) << 8)
                | ord(byte_str[i + 2])
            )
        elif i + 1 < len(byte_str):
            n = (ord(byte_str[i]) << 16) | (ord(byte_str[i + 1]) << 8)
        else:
            n = ord(byte_str[i]) << 16
        for j, mask in zip(range(18, -1, -6), (0xFC0000, 0x03F000, 0x0FC0, 0x3F)):
            if j == 6 and i + 1 >= len(byte_str):
                break
            if j == 0 and i + 2 >= len(byte_str):
                break
            out.append(alphabet[(n & mask) >> j])
    out.append("=" * ((4 - len(out) % 4) % 4))
    return "".join(out)


def _transform_bytes(big_array: list[int], byte_values: list[int]) -> str:
    """256 字节状态机的置换混淆；原位修改 big_array（与上游一致，跨调用演化）。"""
    result: list[str] = []
    index_b = big_array[1]
    initial_value = 0
    value_e = 0
    for index, item in enumerate(byte_values):
        if index == 0:
            initial_value = big_array[index_b]
            sum_initial = index_b + initial_value
            big_array[1] = initial_value
            big_array[index_b] = index_b
        else:
            sum_initial = initial_value + value_e
        sum_initial %= len(big_array)
        result.append(chr(item ^ big_array[sum_initial]))
        value_e = big_array[(index + 2) % len(big_array)]
        sum_initial = (index_b + value_e) % len(big_array)
        initial_value = big_array[sum_initial]
        big_array[sum_initial] = big_array[(index + 2) % len(big_array)]
        big_array[(index + 2) % len(big_array)] = initial_value
        index_b = sum_initial
    return "".join(result)


def generate_random_bytes(length: int = 3) -> str:
    """生成混淆用伪随机字节串（每次调用消费 length 次 random.random()）。"""

    def sequence() -> list[str]:
        rd = int(random.random() * 10000)
        return [
            chr(((rd & 255) & 170) | 1),
            chr(((rd & 255) & 85) | 2),
            chr((_js_shift_right(rd, 8) & 170) | 5),
            chr((_js_shift_right(rd, 8) & 85) | 40),
        ]

    result: list[str] = []
    for _ in range(length):
        result.extend(sequence())
    return "".join(result)


def generate_fingerprint(platform: str = "Win32") -> str:
    """生成模拟浏览器环境指纹（a_bogus 输入之一，同一 transport 实例内保持不变）。"""
    inner_width = random.randint(1024, 1920)
    inner_height = random.randint(768, 1080)
    outer_width = inner_width + random.randint(24, 32)
    outer_height = inner_height + random.randint(75, 90)
    size_width = random.randint(1024, 1920)
    size_height = random.randint(768, 1080)
    avail_width = random.randint(1280, 1920)
    avail_height = random.randint(800, 1080)
    screen_y = random.choice([0, 30])
    return (
        f"{inner_width}|{inner_height}|{outer_width}|{outer_height}|"
        f"0|{screen_y}|0|0|{size_width}|{size_height}|"
        f"{avail_width}|{avail_height}|{inner_width}|{inner_height}|24|24|{platform}"
    )


class ABogus:
    """a_bogus 参数生成器（签名结果与 UA/指纹/时间戳绑定）。"""

    def __init__(
        self,
        fp: str = "",
        user_agent: str = "",
        options: list[int] | None = None,
    ) -> None:
        self.aid = AID
        self.page_id = PAGE_ID
        self.salt = SALT
        self.options = options if options is not None else list(OPTIONS_GET)
        self.ua_key = UA_KEY
        self.user_agent = user_agent or DEFAULT_USER_AGENT
        self.browser_fp = fp or generate_fingerprint()
        self._big_array = list(_BIG_ARRAY)

    def _params_to_array(self, param: str | list[int], add_salt: bool = True) -> list[int]:
        if isinstance(param, str) and add_salt:
            param = param + self.salt
        return _sm3_to_array(param)

    def generate_abogus(self, params: str, body: str = "") -> tuple[str, str, str, str]:
        """对查询串签名。

        Args:
            params: 已按目标接口拼好的 query 串（原样签名，不做 urlencode）。
            body: 请求体（GET 接口恒为空串）。

        Returns:
            ``(含 a_bogus 的 query, a_bogus, user_agent, body)``。
        """
        ab_dir: dict[int, Any] = {
            8: 3,
            15: {
                "aid": self.aid,
                "pageId": self.page_id,
                "boe": False,
                "ddrt": 8.5,
                "paths": [
                    "^/webcast/",
                    "^/aweme/v1/",
                    "^/aweme/v2/",
                    "/v1/message/send",
                    "^/live/",
                    "^/captcha/",
                    "^/ecom/",
                ],
                "track": {"mode": 0, "delay": 300, "paths": []},
                "dump": True,
                "rpU": "",
            },
            18: 44,
            19: [1, 0, 1, 0, 1],
            66: 0,
            69: 0,
            70: 0,
            71: 0,
        }

        start_encryption = int(time.time() * 1000)
        array1 = self._params_to_array(self._params_to_array(params))
        array2 = self._params_to_array(self._params_to_array(body))
        array3 = self._params_to_array(
            _custom_b64_encode(
                "".join(chr(b) for b in _rc4_encrypt(self.ua_key, self.user_agent)),
                ALPHABET_SECONDARY,
            ),
            add_salt=False,
        )
        end_encryption = int(time.time() * 1000)

        ab_dir[20] = (start_encryption >> 24) & 255
        ab_dir[21] = (start_encryption >> 16) & 255
        ab_dir[22] = (start_encryption >> 8) & 255
        ab_dir[23] = start_encryption & 255
        ab_dir[24] = int(start_encryption / 256 / 256 / 256 / 256) >> 0
        ab_dir[25] = int(start_encryption / 256 / 256 / 256 / 256 / 256) >> 0

        ab_dir[26] = (self.options[0] >> 24) & 255
        ab_dir[27] = (self.options[0] >> 16) & 255
        ab_dir[28] = (self.options[0] >> 8) & 255
        ab_dir[29] = self.options[0] & 255

        ab_dir[30] = int(self.options[1] / 256) & 255
        ab_dir[31] = (self.options[1] % 256) & 255
        ab_dir[32] = (self.options[1] >> 24) & 255
        ab_dir[33] = (self.options[1] >> 16) & 255

        ab_dir[34] = (self.options[2] >> 24) & 255
        ab_dir[35] = (self.options[2] >> 16) & 255
        ab_dir[36] = (self.options[2] >> 8) & 255
        ab_dir[37] = self.options[2] & 255

        ab_dir[38] = array1[21]
        ab_dir[39] = array1[22]
        ab_dir[40] = array2[21]
        ab_dir[41] = array2[22]
        ab_dir[42] = array3[23]
        ab_dir[43] = array3[24]

        ab_dir[44] = (end_encryption >> 24) & 255
        ab_dir[45] = (end_encryption >> 16) & 255
        ab_dir[46] = (end_encryption >> 8) & 255
        ab_dir[47] = end_encryption & 255
        ab_dir[48] = ab_dir[8]
        ab_dir[49] = int(end_encryption / 256 / 256 / 256 / 256) >> 0
        ab_dir[50] = int(end_encryption / 256 / 256 / 256 / 256 / 256) >> 0

        ab_dir[51] = (self.page_id >> 24) & 255
        ab_dir[52] = (self.page_id >> 16) & 255
        ab_dir[53] = (self.page_id >> 8) & 255
        ab_dir[54] = self.page_id & 255
        ab_dir[55] = self.page_id
        ab_dir[56] = self.aid
        ab_dir[57] = self.aid & 255
        ab_dir[58] = (self.aid >> 8) & 255
        ab_dir[59] = (self.aid >> 16) & 255
        ab_dir[60] = (self.aid >> 24) & 255

        ab_dir[64] = len(self.browser_fp)
        ab_dir[65] = len(self.browser_fp)

        sorted_values = [ab_dir.get(i, 0) for i in _SORT_INDEX]
        fingerprint_array = [ord(char) for char in self.browser_fp]
        ab_xor = (len(self.browser_fp) & 255) >> 8 & 255
        for index in range(len(_SORT_INDEX_2) - 1):
            if index == 0:
                ab_xor = ab_dir.get(_SORT_INDEX_2[index], 0)
            ab_xor ^= ab_dir.get(_SORT_INDEX_2[index + 1], 0)

        sorted_values.extend(fingerprint_array)
        sorted_values.append(ab_xor)

        payload = generate_random_bytes() + _transform_bytes(self._big_array, sorted_values)
        abogus = _abogus_encode(payload, ALPHABET_PRIMARY)
        return (f"{params}&a_bogus={abogus}", abogus, self.user_agent, body)
