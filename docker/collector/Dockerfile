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

# 剪枝 stage：供运行时 COPY 源码用（不用 COPY --exclude——CI 的 buildx
# 内建 frontend 不认该 flag，本地新 frontend 才支持，曾致流水线确定性失败）
FROM backend-builder AS backend-pruned
RUN rm -rf /app/.venv /app/tests

FROM python:3.11-slim-bookworm

WORKDIR /app

# 社媒 ASR 流水线依赖 ffmpeg 抽音轨（缺失时全部降级 ffmpeg_unavailable）
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY --from=backend-builder /app/.venv /app/.venv
# 与 web 镜像同约定：源码经 backend-pruned stage（已 rm .venv/tests），
# 避免 venv 双份与测试代码入运行时
COPY --from=backend-pruned /app /app
# 助手 Skills：settings.skills_dir 在容器内解析为 /skills（与 web 镜像一致）
COPY skills/ /skills/

ENV PYTHONUNBUFFERED=1
ENV COLLECT_TASK=default
# 脱离 compose 单独运行时容器本地时间仍为北京墙钟；compose 注入的同名变量优先级更高
ENV TZ=Asia/Shanghai
ENV PATH="/app/.venv/bin:$PATH"

COPY docker/collector/entrypoint-collector.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
