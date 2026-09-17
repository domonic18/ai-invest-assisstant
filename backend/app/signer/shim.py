"""页面注入脚本与签名协议常量（单点跟版层）。

Capture-shim 与 SIGN_SCRIPT 改编自 Douyin_TikTok_Download_API
docker/browser_rpc/backends/cloak.py（Apache-2.0 License）© Evil0ctal
https://github.com/Evil0ctal/Douyin_TikTok_Download_API

原理（2026-09 实测，见上游注释）：抖音页面 SDK 无任何可调用签名函数——它
patch window.fetch 与 XMLHttpRequest 在传输层签名，算法跑在字节码 VM 内。
唯一取签名的方法是把请求递给 SDK 本尊：init script 装在页面脚本之前
（处于 SDK patch 的下层），capture 时 SDK 改写后的 URL 落到 state.url
随即 abort——签名零上游请求成本。

SIGN_SCRIPT 用差集返回 SDK 追加的「任意」参数名，不硬编码参数集：
灰度期参数集会变（当前为 a_bogus/verifyFp/fp/uifid/timestamp/
x-secsdk-web-signature），硬编码表会在平台加参时静默丢参。
"""

from __future__ import annotations

SIGNING_ORIGIN = "https://www.douyin.com"

# zjzcap 作为 state 键名前缀，避免与页面全局变量撞名
CAPTURE_INIT_SCRIPT = """
(() => {
  const nativeFetch = window.fetch;
  const nativeOpen = XMLHttpRequest.prototype.open;
  const state = { capture: false, url: null };
  window.__zjzcap = state;

  window.fetch = function (input, init) {
    const url = typeof input === 'string' ? input : (input && input.url);
    if (state.capture) {
      state.url = url;
      // 绝不触达网络：走到这里时 SDK 已完成改写
      return Promise.reject(new DOMException('zjz-capture', 'AbortError'));
    }
    return nativeFetch.apply(this, arguments);
  };

  XMLHttpRequest.prototype.open = function (method, url) {
    if (state.capture) {
      state.url = url;
      throw new DOMException('zjz-capture', 'AbortError');
    }
    return nativeOpen.apply(this, arguments);
  };
})();
"""

SIGN_SCRIPT = """
async (input) => {
  const state = window.__zjzcap;
  if (!state) return { error: 'capture shim not installed' };

  const target = input.query ? `${input.url}?${input.query}` : input.url;
  const before = new Set([...new URL(target).searchParams.keys()]);

  state.capture = true;
  state.url = null;
  try {
    await window.fetch(target, { method: input.method || 'GET' });
  } catch (e) {
    // AbortError 是预期路径：shim 拦下了
  } finally {
    state.capture = false;
  }

  if (!state.url) return { error: 'the SDK did not dispatch a request' };
  const signed = new URL(state.url, location.origin);
  const added = {};
  for (const [k, v] of signed.searchParams) {
    if (!before.has(k)) added[k] = v;
  }
  return Object.keys(added).length ? { params: added } : { error: 'the SDK added nothing' };
}
"""

# 就绪探测：页面可导航 ≠ 可签名（security bundle 后到）。平坦频率探测会把
# 页面探崩（上游实测 ~100 次/25s 后 Target crashed），退避给 ~15 次。
READY_POLL_SECONDS = 0.25
READY_POLL_GROWTH = 1.6
READY_POLL_MAX_SECONDS = 2.5
READY_MAX_CONSECUTIVE_ERRORS = 3

# Chromium 启动参数：去 webdriver 指纹（SDK 会查）+ 容器 /dev/shm 兜底
CHROMIUM_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
]
