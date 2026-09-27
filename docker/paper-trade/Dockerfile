# 掘金线上仿真交易 REST 网关 sidecar：gmtrade SDK 的云端 TCP 网关已废弃（SDK 2023-10 停更），
# 改接 sim.myquant.cn 网页版同款 REST 柜台（discovery 服务发现 + token 作 Bearer，见 main.py 头注释）。
# 依赖仅 fastapi/uvicorn/httpx 纯 Python，脱离 backend/pyproject 独立 requirements，无平台限制。
FROM python:3.12-slim-bookworm

WORKDIR /app
# 境内构建走清华镜像（与 docker/signer 同约定）
ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py ./

EXPOSE 8020
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8020"]
