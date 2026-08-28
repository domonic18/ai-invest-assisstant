FROM python:3.11-slim-bookworm AS backend-builder

WORKDIR /app
# 国内服务器/本地构建均走清华镜像（pip 不读 UV_DEFAULT_INDEX，需单独配置）
ENV UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
# 依赖层：先按 uv.lock 精确安装（--frozen 禁止重解析），源码变更不使缓存失效
COPY backend/pyproject.toml backend/uv.lock ./
RUN pip install --no-cache-dir uv \
    && uv sync --frozen --no-dev --no-install-project
COPY backend/ .
RUN uv sync --frozen --no-dev

FROM python:3.11-slim-bookworm

WORKDIR /app

COPY --from=backend-builder /app/.venv /app/.venv
COPY --from=backend-builder /app /app

ENV PYTHONUNBUFFERED=1
ENV COLLECT_TASK=default
ENV PATH="/app/.venv/bin:$PATH"

COPY docker/collector/entrypoint-collector.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
