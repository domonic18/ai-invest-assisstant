"""SM3 密码杂凑算法内联实现（GM/T 0004-2012）。

a_bogus 签名仅用到 SM3 一处，为避免引入 gmssl 依赖而内联；
输入输出与 gmssl 的 ``sm3.sm3_hash(func.bytes_to_list(data))`` 等价。
"""

_IV = (
    0x7380166F,
    0x4914B2B9,
    0x172442D7,
    0xDA8A0600,
    0xA96F30BC,
    0x163138AA,
    0xE38DEE4D,
    0xB0FB0E4E,
)


def _rotl(x: int, n: int) -> int:
    """32 位循环左移。"""
    return ((x << n) & 0xFFFFFFFF) | (x >> (32 - n))


def _p0(x: int) -> int:
    return x ^ _rotl(x, 9) ^ _rotl(x, 17)


def _p1(x: int) -> int:
    return x ^ _rotl(x, 15) ^ _rotl(x, 23)


def sm3_hash(data: bytes) -> str:
    """计算 SM3 摘要。

    Args:
        data: 输入字节串。

    Returns:
        64 位十六进制摘要字符串。
    """
    msg = bytearray(data)
    bit_len = len(data) * 8
    msg.append(0x80)
    while len(msg) % 64 != 56:
        msg.append(0)
    msg += bit_len.to_bytes(8, "big")

    v = list(_IV)
    for offset in range(0, len(msg), 64):
        block = msg[offset : offset + 64]
        w = [int.from_bytes(block[i : i + 4], "big") for i in range(0, 64, 4)]
        for j in range(16, 68):
            w.append(
                _p1(w[j - 16] ^ w[j - 9] ^ _rotl(w[j - 3], 15))
                ^ _rotl(w[j - 13], 7)
                ^ w[j - 6]
            )
        w1 = [w[j] ^ w[j + 4] for j in range(64)]

        a, b, c, d, e, f, g, h = v
        for j in range(64):
            t = 0x79CC4519 if j < 16 else 0x7A879D8A
            ss1 = _rotl((_rotl(a, 12) + e + _rotl(t, j % 32)) & 0xFFFFFFFF, 7)
            ss2 = ss1 ^ _rotl(a, 12)
            if j < 16:
                ff = a ^ b ^ c
                gg = e ^ f ^ g
            else:
                ff = (a & b) | (a & c) | (b & c)
                gg = (e & f) | (~e & g)
            tt1 = (ff + d + ss2 + w1[j]) & 0xFFFFFFFF
            tt2 = (gg + h + ss1 + w[j]) & 0xFFFFFFFF
            d = c
            c = _rotl(b, 9)
            b = a
            a = tt1
            h = g
            g = _rotl(f, 19)
            f = e
            e = _p0(tt2)
        v = [x ^ y for x, y in zip(v, (a, b, c, d, e, f, g, h))]

    return "".join(f"{x:08x}" for x in v)
