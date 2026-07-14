# backend-builder
FROM python:3.11-slim-bookworm AS backend-builder
WORKDIR /app
COPY backend/pyproject.toml .
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple \
    && pip install --no-cache-dir -e .
COPY backend/ .

# frontend-builder
FROM node:20-alpine AS frontend-builder

ARG NPM_REGISTRY=https://registry.npmmirror.com
RUN npm config set registry ${NPM_REGISTRY}

# Build the shared package first (web depends on it via file:../shared)
WORKDIR /shared
COPY shared/package.json ./
RUN npm install
COPY shared/ ./
RUN npm run build

WORKDIR /web
COPY web/package.json web/pnpm-lock.yaml* web/package-lock.json* ./
RUN npm install -g pnpm && pnpm config set registry ${NPM_REGISTRY} && \
    pnpm install --no-frozen-lockfile || npm install
COPY web/ .
RUN pnpm build || npm run build

# runtime
FROM python:3.11-slim-bookworm

RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g; s|security.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources; \
    fi; \
    if [ -f /etc/apt/sources.list ]; then \
        sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g; s|security.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list; \
    fi; \
    apt-get update && apt-get install -y --no-install-recommends \
    nginx supervisor curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=backend-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=backend-builder /usr/local/bin /usr/local/bin
COPY --from=backend-builder /app /app
COPY --from=frontend-builder /web/dist /usr/share/nginx/html

COPY docker/web/nginx.conf /etc/nginx/nginx.conf
COPY docker/web/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

EXPOSE 9000
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
