# 部署与运维方案（腾讯云版）

## 1. 部署架构总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              腾讯云 部署架构                                  │
│                                                                              │
│  ┌─────────────────────────────────────────┐  ┌───────────────────────────┐ │
│  │         腾讯云函数 SCF (Web 函数)         │  │  腾讯云轻量应用服务器       │ │
│  │                                         │  │  (Lighthouse 4核16G)      │ │
│  │  ┌───────────────────────────────────┐  │  │                           │ │
│  │  │     单一 Docker 镜像 (all-in-one)   │  │  │  ┌─────────────────────┐ │ │
│  │  │                                   │  │  │  │ PostgreSQL           │ │ │
│  │  │  ┌─────────┐  ┌───────────────┐  │  │  │  │ (TimescaleDB)       │ │ │
│  │  │  │ Nginx   │  │ FastAPI 后端   │  │  │  │  │ :5432               │ │ │
│  │  │  │ :9000   │→ │ :8000         │  │  │  │  └─────────────────────┘ │ │
│  │  │  │         │  │               │  │  │  │                           │ │
│  │  │  │ /       │  │ /api/* 业务接口│  │  │  │  ┌─────────────────────┐ │ │
│  │  │  │ (React) │  │ /ws   实时推送 │  │  │  │  │ Redis               │ │ │
│  │  │  │         │  │ /api/auth/wx- │  │  │  │  │ :6379               │ │ │
│  │  │  │         │  │ login(小程序) │  │  │  │  └─────────────────────┘ │ │
│  │  │  └─────────┘  └───────────────┘  │  │  │                           │ │
│  │  └───────────────────────────────────┘  │  │  ┌─────────────────────┐ │ │
│  │                                         │  │  │ Elasticsearch       │ │ │
│  │  域名: api.your-domain.com              │  │  │ :9200               │ │ │
│  │  ←── 浏览器 (Web端)                     │  │  └─────────────────────┘ │ │
│  │  ←── 微信小程序 (移动端)                 │  │                           │ │
│  └─────────────────────────────────────────┘  │  ┌─────────────────────┐ │ │
│                                                │  │ Milvus Standalone   │ │ │
│  ┌─────────────────────────────────────────┐  │  │ :19530              │ │ │
│  │    腾讯云函数 SCF (Job 函数 — 定时触发)   │  │  └─────────────────────┘ │ │
│  │                                         │  │                           │ │
│  │  ┌───────────────────────────────────┐  │  │  ┌─────────────────────┐ │ │
│  │  │     采集 Job 镜像 (独立)           │  │  │  │ MinIO               │ │ │
│  │  │                                   │  │  │  │ :9000 (API)         │ │ │
│  │  │  ┌──────────┐  ┌──────────────┐  │  │  │  │ :9001 (Console)     │ │ │
│  │  │  │ 定时触发器│→ │ Scrapy 采集   │  │──┼──┼──┤  └─────────────────────┘ │ │
│  │  │  │ (Timer)  │  │ + akshare    │  │  │  │                           │ │
│  │  │  └──────────┘  │ + Playwright │  │  │  │  所有服务通过 Docker       │ │
│  │  │                 │              │  │  │  │  Compose 统一管理          │ │
│  │  │                 │ 写入 PG/ES/  │  │  │                           │ │
│  │  │                 │ MinIO/Milvus │  │  │                           │ │
│  │  │                 └──────────────┘  │  │                           │ │
│  │  └───────────────────────────────────┘  │                           │ │
│  │                                         │                           │ │
│  │  异步执行，最长 24h                       │  内网互通 (VPC / 公网 IP)   │ │
│  └─────────────────────────────────────────┘                           │ │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 2. 微信小程序部署说明

小程序端不部署在腾讯云上，而是通过微信开发者工具上传至微信平台。

### 2.1 小程序发布流程

```
开发完成 (Taro build)
    │
    ▼
上传至微信开发者工具
    │
    ▼
提交审核 (微信平台)
    │
    ▼
审核通过 → 发布上线
```

### 2.2 小程序后端配置

小程序通过 HTTPS 调用 SCF Web 函数的 API：

```typescript
// miniapp/src/utils/request.ts
const API_BASE = 'https://api.your-domain.com/api/v1';

export async function request<T>(options: {
  url: string;
  method?: 'GET' | 'POST';
  data?: any;
}): Promise<T> {
  const token = Taro.getStorageSync('access_token');
  
  const res = await Taro.request({
    url: `${API_BASE}${options.url}`,
    method: options.method || 'GET',
    data: options.data,
    header: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  
  return res.data as T;
}
```

### 2.3 小程序 AppID 与服务器域名配置

在微信公众平台 → 开发管理 → 开发设置中配置：

```
request 合法域名: https://api.your-domain.com
socket 合法域名: wss://api.your-domain.com
```

> 域名必须为已备案的 HTTPS 域名。腾讯云 API 网关自带 HTTPS 证书，配置自定义域名映射即可。

## 4. 前后端合一 Dockerfile（Web 函数镜像）

> 完整项目目录结构参见 [docs/arch/00-overview.md](./00-overview.md)。

```dockerfile
# docker/web/Dockerfile
FROM python:3.11-slim AS backend-builder
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .

FROM node:20-alpine AS frontend-builder
WORKDIR /web
COPY web/package.json web/pnpm-lock.yaml ./
RUN npm install -g pnpm && pnpm install --frozen-lockfile
COPY web/ .
RUN pnpm build
# 产物: /web/dist/

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx supervisor curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
# 复制后端
COPY --from=backend-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=backend-builder /app /app
# 复制前端
COPY --from=frontend-builder /web/dist /usr/share/nginx/html
# 配置
COPY docker/web/nginx.conf /etc/nginx/nginx.conf
COPY docker/web/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

EXPOSE 9000
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
```

## 5. 部署流程

### 5.1 轻量服务器（一次性部署）

```bash
# 1. 腾讯云控制台购买轻量服务器，Ubuntu 22.04，4核16GB，挂载 500GB 数据盘

# 2. SSH 初始化
ssh root@<IP>
mkfs.ext4 /dev/vdb && mkdir -p /data && mount /dev/vdb /data
echo "/dev/vdb /data ext4 defaults 0 0" >> /etc/fstab

# 3. 安装 Docker
curl -fsSL https://get.docker.com | sh

# 4. 上传 docker-compose.infra.yml / .env / docker/database/init-scripts/
scp docker-compose.infra.yml .env root@<IP>:/opt/investment/
scp -r docker/database/init-scripts/ root@<IP>:/opt/investment/docker/database/

# 5. 启动
cd /opt/investment
docker compose -f docker-compose.infra.yml up -d
docker compose -f docker-compose.infra.yml ps
```

### 5.2 云函数镜像构建与推送

```bash
# Web 函数
docker build -t ccr.ccs.tencentyun.com/investment/web-api:latest -f docker/web/Dockerfile .
docker push ccr.ccs.tencentyun.com/investment/web-api:latest

# 采集 Job
docker build -t ccr.ccs.tencentyun.com/investment/collector:latest -f docker/collector/Dockerfile .
docker push ccr.ccs.tencentyun.com/investment/collector:latest
```

### 5.3 云函数创建

**Web 函数**：
- 镜像: `ccr.ccs.tencentyun.com/investment/web-api:latest`
- 端口: 9000 / 内存: 2048MB / 超时: 60s
- 触发器: API 网关 → 绑定域名

**Job 函数** × N：
- 镜像: `ccr.ccs.tencentyun.com/investment/collector:latest`
- 环境变量: `COLLECT_TASK=kline` (按任务不同)
- 触发器: Timer 定时触发

### 5.4 微信小程序发布

```bash
# 1. 构建小程序代码
cd miniapp
npm run build:weapp

# 2. 打开微信开发者工具
#    导入 miniapp/dist/ 目录

# 3. 预览 → 上传代码 → 提交审核
```

## 6. 成本估算

```
Web 函数: ~¥72/月 (含预置并发)
Job 函数 (4个): ~¥33/月
轻量服务器: ~¥300-400/月
云硬盘 500GB: ~¥175/月
═══════════════════════════════
  合计: ~¥580-680/月
  (+ 域名备案 ¥0，微信小程序认证 ¥300/年)
```
