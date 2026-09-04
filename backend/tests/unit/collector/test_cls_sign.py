"""cls 签名与 sv 提取测试（向量来自 2026-09 探针实测规则推演）。"""

import hashlib

import pytest

from collector.spiders.cls_sign import DEFAULT_SV, build_cls_sign, extract_sv


def _reference_sign(query: str) -> str:
    sha1_hex = hashlib.sha1(query.encode()).hexdigest()
    return hashlib.md5(sha1_hex.encode()).hexdigest()


@pytest.mark.unit
class TestBuildClsSign:
    def test_probe_vector(self) -> None:
        params = {
            "app": "CailianpressWeb",
            "os": "web",
            "sv": "8.7.9",
            "refresh_type": "1",
            "rn": "20",
            "last_time": "0",
        }
        expected = _reference_sign(
            "app=CailianpressWeb&last_time=0&os=web&refresh_type=1&rn=20&sv=8.7.9"
        )
        assert expected == "e11ef7d616d8f9a2f056e6df1aefc4d4"
        assert build_cls_sign(params) == expected

    def test_keys_sorted_case(self) -> None:
        assert build_cls_sign({"b": "2", "a": "1"}) == _reference_sign("a=1&b=2")

    def test_non_string_values(self) -> None:
        assert build_cls_sign({"rn": 20, "last_time": 0}) == _reference_sign(
            "last_time=0&rn=20"
        )


@pytest.mark.unit
class TestExtractSv:
    def test_from_bundle_pattern(self) -> None:
        html = '<script src="/_app/immutable/chunks/index.js"></script><script>var cfg={sv:"9.1.2",os:"web"}</script>'
        assert extract_sv(html) == "9.1.2"

    def test_fallback_default(self) -> None:
        assert extract_sv("<html><body>blocked</body></html>") == DEFAULT_SV
