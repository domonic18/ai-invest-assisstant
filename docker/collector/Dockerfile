FROM python:3.11-slim-bookworm AS backend-builder

WORKDIR /app
COPY backend/pyproject.toml .
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple \
    && pip install --no-cache-dir -e .
COPY backend/ .

FROM python:3.11-slim-bookworm

WORKDIR /app

COPY --from=backend-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=backend-builder /usr/local/bin /usr/local/bin
COPY --from=backend-builder /app /app

ENV PYTHONUNBUFFERED=1
ENV COLLECT_TASK=default

COPY docker/collector/entrypoint-collector.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
