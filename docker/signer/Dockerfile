# 抖音签名 sidecar：Playwright chromium + douyin.com warm 页 capture-shim
# 不锁 platform：chromium 原生 arm64/amd64 均可用，amd64 模拟反而破坏浏览器指纹
#
# 境内本地构建：pythonhosted/playwright CDN 间歇性 TLS 阻断（容器内复现）。
# wheel 走清华（uv.lock 的 /packages/ 路径与官方 CDN 同构，构建期改写，
# wheel 哈希一致）；浏览器二进制无同构国内镜像（npmmirror 无新 cft 布局，
# 华为云为目录页假 200），经构建代理走宿主机梯子：
#   HTTPS_PROXY=http://host.docker.internal:7897 docker compose build douyin-signer
# CI 境外网络直连，无需设置代理。
FROM python:3.11-slim-bookworm

WORKDIR /app
# 国内服务器/本地构建均走清华镜像（pip 不读 UV_DEFAULT_INDEX，需单独配置）
ENV UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

# 依赖层：先按 uv.lock 精确安装（--frozen 禁止重解析），playwright 只在 signer 组
COPY backend/pyproject.toml backend/uv.lock ./
RUN sed -i 's|https://files.pythonhosted.org|https://pypi.tuna.tsinghua.edu.cn|g' uv.lock \
    && pip install --no-cache-dir uv \
    && uv sync --frozen --no-dev --group signer --no-install-project
COPY backend/ .
RUN sed -i 's|https://files.pythonhosted.org|https://pypi.tuna.tsinghua.edu.cn|g' uv.lock \
    && uv sync --frozen --no-dev --group signer \
    && uv run playwright install --with-deps chromium

ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8010
# 内网无鉴权（compose 私有网络）；/health 永远可答
CMD ["uvicorn", "app.signer.main:app", "--host", "0.0.0.0", "--port", "8010"]
