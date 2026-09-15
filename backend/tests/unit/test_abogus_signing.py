"""a_bogus 签名移植测试：黄金样本对拍（原版 f2 + gmssl 生成）+ SM3 标准向量。

黄金样本生成方式：固定 time.time=1757879400.0、random.seed(42)、固定 UA/指纹，
用原版 f2/utils/abogus.py（gmssl SM3）运行输出；移植实现必须逐字节一致。
"""

import random
import time

import pytest

from app.adapters.douyin._sm3 import sm3_hash
from app.adapters.douyin.signing import ABogus, generate_random_bytes

FIXED_TS = 1757879400.0

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0"
)
FINGERPRINT = "1568|943|1592|1020|0|30|0|0|1280|1024|1440|900|1568|943|24|24|Win32"

PARAMS_GET = (
    "device_platform=webapp&aid=6383&channel=channel_pc_web"
    "&aweme_id=7380308675841297704&update_version_code=170400&pc_client_type=1"
    "&version_code=190500&version_name=19.5.0&cookie_enabled=true"
    "&screen_width=1920&screen_height=1080&browser_language=zh-CN"
    "&browser_platform=Win32&browser_name=Edge&browser_version=125.0.0.0"
    "&browser_online=true&engine_name=Blink&engine_version=125.0.0.0"
    "&os_name=Windows&os_version=10&cpu_core_num=12&device_memory=8&platform=PC"
    "&downlink=10&effective_type=4g&round_trip_time=50&webid=7376294349792396827"
)
PARAMS_POST = (
    "device_platform=webapp&aid=6383&channel=channel_pc_web&pc_client_type=1"
    "&pc_libra_divert=Windows&update_version_code=170400&support_h265=1"
    "&support_dash=0&version_code=170400&version_name=17.4.0&cookie_enabled=true"
    "&screen_width=1920&screen_height=1080&browser_language=zh-CN"
    "&browser_platform=Win32&browser_name=Edge&browser_version=131.0.0.0"
    "&browser_online=true&engine_name=Blink&engine_version=131.0.0.0"
    "&os_name=Windows&os_version=10&cpu_core_num=12&device_memory=8&platform=PC"
    "&downlink=10&effective_type=4g&round_trip_time=50"
)
BODY_POST = "aweme_type=0&item_id=7467485482314763572&play_delta=1&source=0"

GOLDEN_GET = (
    "O7m0/QzVkVxPhESY5W9LfY3q61l3YQx70SVkMD2fgVfPDg39HMTD9exEHT7vn88ji4/"
    "sIeEjy4hbT3nBrQCy0qwf9WwE/2CZmL00t-Ph5xSSs1feeL6DrsJx-kJ-Fee/"
    "-vV3xcv0y75CKms0WoCjmhK4bfebY7Y6i6trhE=="
)
GOLDEN_POST = (
    "O7m0/QzVkVxPhESY5W9LfY3q657wYQx70SVkMD2fSOgPDg39HMTD9exoHT7vn88ji4/"
    "sIeEjy4hbT3nBrQCy0qwf9WwE/2CZmL00t-Ph5xSSs1feeL6DrsJx-kJ-Fee/"
    "-vV3xcv0y75CKms0WoCjmhK4bfebY7Y6i6tr2E=="
)


@pytest.fixture(autouse=True)
def _fixed_time(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time, "time", lambda: FIXED_TS)


class TestSm3:
    def test_standard_vector_short(self) -> None:
        assert (
            sm3_hash(b"abc")
            == "66c7f0f462eeedd9d1f2d46bdc10e4e24167c4875cf2f7a2297da02b8f4ba8e0"
        )

    def test_standard_vector_long(self) -> None:
        assert (
            sm3_hash(b"abcd" * 16)
            == "debe9ff92275b8a138604889c18e5a4d6fdb70e5387e5765293dcba39c0c5732"
        )

    def test_empty_input(self) -> None:
        assert len(sm3_hash(b"")) == 64


class TestABogusGolden:
    """与原版 f2 实现的逐字节对拍（签名算法跟版的回归锚）。"""

    def test_get_request_matches_upstream(self) -> None:
        random.seed(42)
        abogus = ABogus(user_agent=USER_AGENT, fp=FINGERPRINT, options=[0, 1, 8])
        result = abogus.generate_abogus(params=PARAMS_GET)
        assert result[1] == GOLDEN_GET
        assert result[0] == f"{PARAMS_GET}&a_bogus={GOLDEN_GET}"
        assert result[2] == USER_AGENT
        assert result[3] == ""

    def test_post_request_matches_upstream(self) -> None:
        random.seed(42)
        abogus = ABogus(user_agent=USER_AGENT, fp=FINGERPRINT, options=[0, 1, 14])
        result = abogus.generate_abogus(params=PARAMS_POST, body=BODY_POST)
        assert result[1] == GOLDEN_POST

    def test_output_length_in_expected_band(self) -> None:
        random.seed(7)
        abogus = ABogus(user_agent=USER_AGENT, fp=FINGERPRINT)
        for _ in range(20):
            _, value, _, _ = abogus.generate_abogus(params=PARAMS_GET)
            assert len(value) in {164, 168, 172}

    def test_different_time_produces_different_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        random.seed(42)
        first = ABogus(user_agent=USER_AGENT, fp=FINGERPRINT).generate_abogus(
            params=PARAMS_GET
        )[1]
        monkeypatch.setattr(time, "time", lambda: FIXED_TS + 1.0)
        random.seed(42)
        second = ABogus(user_agent=USER_AGENT, fp=FINGERPRINT).generate_abogus(
            params=PARAMS_GET
        )[1]
        assert first != second

    def test_random_bytes_length(self) -> None:
        random.seed(1)
        assert len(generate_random_bytes()) == 12  # 默认 3 组 × 每组 4 字符
