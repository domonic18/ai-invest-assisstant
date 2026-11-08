# 发布与回滚手册（Runbook）

> 部署逻辑唯一入口：`scripts/deploy.sh`。CI 与人工都只调它，命令形态完全一致：
> `bash scripts/deploy.sh --env <staging|prod> --tag <image-tag>`
> （另有只回收镜像的 `bash scripts/deploy.sh --env <staging|prod> --gc-only`，见 §4.1）

## 1. 流水线拓扑

```
PR → backend + web + db-migration-guard + db-incremental-guard   （全绿才继续）
   → docker-web / docker-collector / docker-signer / docker-paper-trade / docker-migrate（构建推 TCR）
   → deploy-staging    （自托管 runner = 本机测试环境，自动）
   → deploy-production （GitHub Environment `production` + 人工审批 + 串行）
   → image-gc          （构建机镜像回收，if: always()，与成败无关）
```

- 镜像 tag = `<branch>-<sha_short>`，**不可变**。不推 `latest`——它是回滚可靠性的前提
  （TCR 对同 digest 的 tag 会连坐删除，`latest` 会被回滚目标顶掉）。
- **迁移镜像 `migrate` 与应用镜像同 tag**：迁移文件与 `migrate.sh` 打进镜像，
  线上执行的迁移与本次发布的代码必然同 commit。
- 生产机**不执行仓库代码**（仓库为 public）。CI 只以受限参数调用服务器上那份
  可评审的 `scripts/deploy.sh`；TCR 凭据只存在服务器侧 `/root/.docker/config.json`。
- 生产发布**不抢占**：`concurrency: deploy-production, cancel-in-progress: false`。

## 2. 首次启用需要准备的东西

| 项 | 位置 | 说明 |
|---|---|---|
| `DEPLOY_SSH_KEY` | GitHub Actions secret | CI → 生产机的私钥；公钥放生产机 `~/.ssh/authorized_keys` |
| `DEPLOY_KNOWN_HOSTS` | GitHub Actions secret | 生产机 host key 指纹（`ssh-keyscan` 取），开启 host key 校验，**不要关** |
| `DEPLOY_HOST` | GitHub Actions variable | 生产机 SSH 目标（`user@host`）；**仓库为 public，不写进 workflow YAML** |
| `DEPLOY_PATH` | GitHub Actions variable | 生产机上的部署目录 |
| `DEPLOY_ROOT` | GitHub Actions variable | 本机测试环境的部署根目录 |
| `production` Environment | GitHub 仓库设置 | 配 required reviewers，作为生产发布的人工闸门 |
| TCR 凭据 | 生产机 `/root/.docker/config.json`（600） | 生产机自己拉镜像，CI 不传 registry 密码 |
| `APP_TAG` | 生产 `.env` | 由 `deploy.sh` 自动写入，**不要手工改** |

> 主机地址与路径一律走仓库变量（Settings → Environments and variables → Actions variables），不进 YAML、不进文档；CI 在前置校验步检查变量是否齐备，缺失即明确失败。

## 3. 日常发布

### 开发 → 本机测试环境（自动）

合并到 `develop` 后：`docker-*` 四个 job 构建推 TCR → `deploy-staging` 把
`scripts/deploy.sh` / `docker-compose*.yml` / `docker/database/` 同步到本机项目目录，
再执行：

```bash
bash scripts/deploy.sh --env staging --tag develop-<sha_short>
```

本机测试环境用的是 **CI 构建并推送的那份镜像**（`docker-compose.ci.yml` 里
`build: !reset null`），不是本机现编的——合入 develop 后验证到的就是将要发布的那份产物。

### 主干 → 生产环境（人工审批）

合并到 `main` 后：`docker-*` 构建推 TCR → `deploy-production` 等 Environment 审批 →
两次 SSH 调用（顺序不可颠倒）：

```bash
# ① 先把新的部署脚本 / compose / 迁移送到服务器（CI 打包直传）
#    传输内容：scripts/deploy.sh、docker/database/、docker/caddy/、docker-compose.prod.yml
#    理由：生产机到 GitHub 的链路不通（实测 github.com 100% 超时），发布不能依赖它
#    注：docker/database/ 传过去只是让宿主机留一份与本次发布同 commit 的迁移文件供排查；
#        真正执行迁移的是 migrate 镜像（见 §4 第 4 步），它才是迁移内容的唯一真相源
tar -czf /tmp/deploy-assets.tar.gz scripts/deploy.sh docker/database docker/caddy docker-compose.prod.yml
scp /tmp/deploy-assets.tar.gz <host>:/tmp/
# 提取必须以 root 执行：服务器上部分目录（如 docker/caddy/）属主为 root，
# 非 root 提取会因覆盖失败而中断发布（2026-11-07 首次发布即栽在这里）
# --no-same-owner：不让归档里的 uid/gid 覆盖服务器属主
ssh <host> sudo bash -s -- <生产部署目录> "$(git rev-parse HEAD)" <迁移文件数> <<'REMOTE'
cd "$1"
tar --no-same-owner -xzf /tmp/deploy-assets.tar.gz
rm -f /tmp/deploy-assets.tar.gz
chmod 755 scripts/deploy.sh
printf '%s\n' "$2" > .deploy-commit
REMOTE
# ② 再执行部署
sudo bash scripts/deploy.sh --env prod --tag main-<sha_short>
```

传输的资产与 `git checkout` 到同一 commit 等价（同一个 `GITHUB_SHA`），
本次发布的完整 sha 由 CI 写入服务器 `.deploy-commit`，供 `.deploy-state.commit` 记录。

同步步骤带**资产落地完整性校验**：`deploy.sh`、compose、`caddy/Caddyfile`、
`caddy/Dockerfile` 缺一即中止，迁移文件数与 CI 侧不一致也中止——
不让半套资产带着进下一步。

## 4. deploy.sh 做了什么（按顺序）

1. **参数校验**：prod 只放行 `^main-[0-9a-f]{7,40}$`，staging 只放行 `^develop-[0-9a-f]{7,40}$`；
   非法 tag 直接退出（防注入、防误传 `latest`）
2. **预检**：docker / compose v2 可用、compose 文件与 `.env` 存在、磁盘余量 ≥ 5G、
   postgres 容器健康、compose 定义了 `migrate` 服务。
   **staging 例外**：测试环境整栈未运行（有意停用）时，预检判定「无任何容器在跑」
   → 记 SKIP 横幅并以 0 退出，不拉镜像、不迁移、不换容器、不改 `.env`；
   CI 另行打 `::warning::` 标注，避免绿灯被读成「已部署」。
   栈还在但 postgres 单独掉了 → 仍硬失败（真故障不豁免）；prod 一律无此豁免。
3. **备份轮转**：`.env` → `.env.bak` → `.env.bak.1` → `.env.bak.2`（最多 3 份），并把 `APP_TAG` 钉到本次 tag
4. **拉镜像**：应用镜像 + 迁移镜像（`migrate`）。拉取失败但本地已有同 tag 镜像时继续走
   （回滚场景下仓库可能不可达）
5. **迁移先行**：`docker compose run --rm --no-deps --pull never -T migrate`——
   迁移由**独立 migrate 镜像**执行（迁移文件打进镜像，与应用代码同 commit），
   宿主机不需要 psql、也不依赖外部同步过来的迁移文件。
   迁移失败 → 中止，旧版本继续服务（零影响）
6. **换容器**：`compose up -d --wait --no-build --pull never`
   （`--pull never` 防止 compose 现场去拉境内拉不到的 Docker Hub 基础镜像）
7. **健康检查**：所有容器 running，且有 healthcheck 的必须 healthy
8. **落状态**：写 `.deploy-state`（current_tag / previous_tag / commit / deployed_at / status）
9. **失败回滚**：任一步失败 → 用 `previous_tag` 重新 pull + up + 复查，
   状态置 `FAILED_ROLLED_BACK`，**保留现场**（日志不删）
10. **清理**：每仓库保留最新 3 个 `<branch>-<sha>` tag（当前 + 2 个回滚目标），
    只跑 `docker image prune -f`（清悬空层，**绝不 `-a`**，否则连回滚目标一起删）。
    清理由**退出兜底**保证：无论成功、失败、跳过还是中途退出都跑一次
    （原先只挂在成功路径末尾，「磁盘余量不足 → 预检失败 → 不清理 → 磁盘永远不足」
    是个闭环）。清理报告会报**实际删除的张数与字节数**；
    过滤落空（本地无该仓库镜像）一律 **WARN**——空结果不是「无需清理」的证据，
    多半是仓库路径写错（`docker images` 按完整仓库名 `registry/namespace/repo` 匹配，
    只给短前缀匹配不到且静默返回空）；
    另有 `latest` 标签镜像时也 **WARN**（项目禁用 `latest` 推送，它不匹配 sha 版本规则、
    既不计入保留额度也不在清理范围，只报不删，删不删由人定）

### 4.1 只回收镜像（`--gc-only`）

```bash
bash scripts/deploy.sh --env staging --gc-only
```

不部署、不碰 `.env`、不碰容器，只按上述规则回收镜像。给 CI 一个**与部署成败无关**
的清理入口——构建机上 CI 把镜像 `load` 进本地 docker，清理只挂在部署路径末尾时，
构建失败或走 main 分支发布（不经本机）都让镜像只增不减。

### 4.2 CI 侧的镜像回收

`.github/workflows/ci.yml` 有一个独立 job `image-gc`：
`if: ${{ always() && !cancelled() && (github.event_name == 'push' || github.event_name == 'workflow_dispatch') }}`，
无论构建与部署成败都跑一次 `deploy.sh --env staging --gc-only`，
与 `deploy-staging` 共用并发组（避免回收与部署同时动本地镜像）。
回收失败不判红（清理是维护动作，染红会把「部署成功」的结论搅浑），看警告与步骤日志。

**不在 PR 上跑**：该 job 会执行仓库里的 `scripts/deploy.sh`，而自托管 runner
是持有 docker 与部署目录权限的开发机。仓库是 public，PR（含 fork）若在此执行，
等于把自托管机开放给任意代码。既有不变量「PR 从不在自托管机上执行仓库代码」必须守住，
故条件里除 `always()` / `!cancelled()` 外还要求事件是 push 或手动触发。

### 4.3 镜像构建推送的可复用流水线

五个镜像的构建推送语义收敛在 `.github/workflows/release-image.yml`
（`on: workflow_call`），`ci.yml` 里只声明「构建哪个镜像、哪个 Dockerfile、什么上下文」。
语义只有一份，改一处漏两处的风险消失。

保留 ai-invest 的**构建与推送分离**：build 只 `load` 进本地 docker
（`push: false` + `load: true`），推送由独立的 `docker push` 步骤做——
buildx 本地缓存保留在构建机上，构建失败可秒级重跑；推送走简单重试。
推送失败自动重试（最多 3 次），成败由 `Conclude push outcome` 步骤裁定：
任一次尝试成功即 job 成功，三次皆败才判红；登录失败单独判定（配置问题，重试无意义）。

**每次推送自带看门狗**：跨境链路推 TCR 会卡住不返回（实测 trend-studio 同链路
`pushing layers` 挂起二十多分钟无进展），而 `docker push` 不认超时参数、
runner 又是 macOS（无 GNU `timeout`），故用「后台进程 + 轮询 `ps` 状态」
实现单次尝试的 600 秒上限：超时就杀掉本次、进入下一次重试。
**没有这个上限，重试就是摆设**——步骤级上限覆盖整轮循环时，
一次挂死即吃光预算，第 2、3 次尝试根本没机会执行。

## 5. 手动回滚

线上出问题时，先看状态文件：

```bash
cat <生产部署目录>/.deploy-state
# current_tag=main-xxxxxxx
# previous_tag=main-yyyyyyy     ← 回滚目标
# status=OK
```

回滚到 `previous_tag`：

```bash
cd <生产部署目录>
sudo bash scripts/deploy.sh --env prod --tag main-yyyyyyy
```

注意：**回滚不会回滚数据库**。迁移是 forward-only 的，回滚旧镜像后新 schema 会留在库里。
新版本的 DDL 必须是旧版本能容忍的（expand-contract：先加列不删列，新旧代码并存期至少一个发布周期）。

## 6. 排障

| 现象 | 排查 |
|---|---|
| 部署卡在拉镜像 | `docker compose -f <compose 文件> pull <service>` 手工复现；看是否 TCR 不可达 |
| 健康检查超时 | `docker compose ps` 看哪个不健康；`docker compose logs --tail 200 <service>` |
| 迁移失败 | 看 `.deploy-state`（应仍是上一版本 status=OK）；修好迁移文件后重跑 deploy.sh |
| 回滚也失败 | 状态 `FAILED_ROLLED_BACK_FAILED`，需人工介入；此时不要清日志 |
| 磁盘告警 | `docker system df`；`deploy.sh` 已按仓库保留 3 个 tag + `docker image prune -f` |
| 清理报「过滤未命中」 | 仓库路径与本地镜像对不上（`docker images` 按完整仓库名匹配）：核对 `docker images` 里的完整路径与 `DEPLOY_NAMESPACE`，别用短前缀 |
| 清理报「删除 0 个镜像」 | 可能是本地本来就只有保留数量以内的版本（正常），也可能是 tag 形态不匹配 `^(main\|develop)-[0-9a-f]{7,40}$`（非 sha tag 不参与清理） |

## 7. 迁移纪律

- `docker/database/migrations/` 是 schema 唯一真相源，`legacy/` 永不执行
- 执行走**独立 migrate 镜像**（`docker/migrate/Dockerfile`）：迁移文件与 `migrate.sh`
  打进镜像，随 `<branch>-<sha>` tag 发布。线上执行的迁移与本次发布的代码必然同 commit，
  宿主机不需要 psql。开发时仍可 `bash docker/database/migrate.sh` 走同一条逻辑
- 台账表 `schema_migrations` exactly-once，每迁移与登记同事务提交；
  **全程单会话 + 会话级 advisory lock**，并发部署排队而不是同时改 schema
- 新迁移必须幂等（`IF NOT EXISTS` / `ON CONFLICT DO NOTHING`），
  CI 有静态检查（`scripts/check_migration_idempotency.py`）拦截
- CI 门禁三条：
  - `db-migration-guard`：空库从零重放 + 幂等重放断言 + **迁移镜像冒烟**
    （用镜像在空库上从零应用、再重放全跳过，证明镜像里的迁移内容是对的）
  - `db-incremental-guard`：**从 origin/main 的 schema 出发**走增量路径，
    再断言增量结果与从零重放结果的列/索引/约束清单完全一致（无 schema 漂移）
