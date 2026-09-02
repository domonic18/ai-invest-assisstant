# backend-builder
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

# frontend-builder
FROM node:20-alpine AS frontend-builder

ARG NPM_REGISTRY=https://registry.npmmirror.com
ARG VITE_APP_VERSION
ENV VITE_APP_VERSION=${VITE_APP_VERSION}
RUN npm config set registry ${NPM_REGISTRY}

# Build the shared package first (web depends on it via file:../shared)
WORKDIR /shared
COPY shared/package.json ./
RUN npm install
COPY shared/ ./
RUN npm run build

WORKDIR /web
RUN npm config set registry ${NPM_REGISTRY}
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ .
RUN npm run build

# runtime — 单 uvicorn 进程直听 9000：API + SPA 静态托管一体，
# 无 nginx/supervisord 启动竞态（端口监听即完整服务，消除冷启动 502 窗口）
FROM python:3.11-slim-bookworm

RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g; s|security.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources; \
    fi; \
    if [ -f /etc/apt/sources.list ]; then \
        sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g; s|security.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list; \
    fi; \
    apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH"
COPY --from=backend-builder /app/.venv /app/.venv
COPY --from=backend-builder /app /app
COPY --from=frontend-builder /web/dist /app/static
# 助手 Skills：settings.skills_dir 在容器内解析为 /skills（/app 的上四级）
COPY skills/ /skills/

ENV STATIC_DIR=/app/static

EXPOSE 9000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9000", "--proxy-headers", "--forwarded-allow-ips=*"]
