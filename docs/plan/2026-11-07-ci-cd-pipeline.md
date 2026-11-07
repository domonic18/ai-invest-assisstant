# CI/CD 流水线方案（2026-11-07）

> 落地文档：发布 / 回滚 / 排障见 [`docs/deployment-runbook.md`](../deployment-runbook.md)。
> 本文只记录**方案与决策**，不重复运行手册内容。

## 1. 背景

发布原先靠人工 SSH 上服务器手敲命令，存在三类硬伤：

1. **发布不可复现**：生产机 `/opt/investment` 是 git clone，工作树有未提交改动，
   迁移文件靠手工拷贝——代码 / 配置 / 迁移三者不对齐，回滚难定位
2. **磁盘无治理**：全链路无 prune / 保留策略，镜像 tag 只增不减
3. **迁移无门禁**：CI 的 `db-migration-guard` 只验过**空库从零重放**，
   真实的「线上 schema → 新 schema」增量路径从未被自动验证；且该 job 不在
   任何 docker job 的 `needs` 里，迁移坏了也拦不住镜像构建

## 2. 目标

PR 合并 develop → 本机测试环境自动更新；合并 main → 生产环境审批后自动更新；
数据库迁移自动执行；镜像与备份文件自动治理。**在安全稳定的前提下提速。**

## 3. 目标拓扑

```
PR → backend + web + db-migration-guard + db-incremental-guard   （全绿才继续）
   → docker-web / docker-collector / docker-signer / docker-paper-trade（构建推 TCR）
   → deploy-staging    （自托管 runner = 本机测试环境，自动）
   → deploy-production （GitHub Environment `production` + 人工审批 + 串行）
```

两条部署 job 复用同一份 `scripts/deploy.sh`，仅 `--env` 不同。

## 4. 关键决策（用户拍板）

| 决策 | 选择 | 理由 |
|---|---|---|
| 生产发布闸门 | **GitHub Environment + required reviewers** | 仓库为 public，Free 计划可用；比「谁改 main 谁发布」可控 |
| 回滚 | **自动回滚镜像**（部署失败自动退到 `previous_tag`） | 故障窗口最短；人工回滚在半夜不可靠 |
| 部署逻辑落点 | **收敛到服务器上一份可评审脚本，CI 经 SSH 调用** | public 仓库 + 生产执行仓库代码 = 生产 RCE 通道，不可接受 |
| 发布前数据库备份 | **暂不做** | 用户决策。缓解靠：每迁移单事务回滚 + expand-contract + 幂等静态检查。后续批次把 PG 备份从「后置池」提到「发布前置」 |

补充设计判断：**停推 `latest`**。它是回滚可靠性的前提——TCR 对同 digest 的 tag 会连坐删除，
`latest` 会被回滚目标顶掉。tag 改为不可变的 `<branch>-<sha_short>`。

## 5. 关键机制

- **单一部署入口** `scripts/deploy.sh`：参数校验 → 预检 → `.env` 备份轮转 + 钉 `APP_TAG` →
  数据库迁移（先行）→ 换容器 → 健康检查 → 落 `.deploy-state` → 失败自动回滚 → 镜像/备份清理
- **迁移先行**：迁移失败即中止，旧版本继续服务；迁移 forward-only，回滚镜像不回滚 schema
- **并发互斥**：迁移全程单 psql 会话 + 会话级 advisory lock，并发部署排队而非同时改 schema
- **镜像治理**：每仓库保留最新 3 个 tag（当前 + 2 个回滚目标），只跑 `docker image prune -f`，
  **绝不 `-a`**（会把回滚目标删掉）
- **CI 门禁**：
  - `db-migration-guard`：空库从零重放 + 幂等重放断言
  - `db-incremental-guard`（新增）：从 `origin/main` 的 schema 出发走增量路径，
    再断言增量结果的列/索引/约束清单与从零重放**完全一致**（无 schema 漂移）
  - `scripts/check_migration_idempotency.py`（新增）：逐条语句静态扫描，
    拦下 `CREATE TABLE` / `ADD COLUMN` / `CREATE INDEX` 缺 `IF NOT EXISTS`、
    `INSERT` 缺 `ON CONFLICT` 的写法（历史文件进豁免名单，forward-only 不可回改）
  - 四个 docker job 的 `needs` 补齐上述守卫——迁移坏了不许出镜像
- **镜像 tag 全链一致**：构建与部署两端都用 `git rev-parse --short=7 "$GITHUB_SHA"`
  算 tag（显式钉长度，不用自动缩写——自动长度随对象库大小漂移，构建机与生产机
  可能算出不同长度）。tag 形如 `main-1a2b3c4`，与 `deploy.sh` 的校验正则一致
- **服务器 git 拉取**：**不走这条路**。实测生产机到 `github.com` **100% 不可达**
  （`git ls-remote` 8/8、`git fetch` 4/4 全部 60s 超时；裸 HTTPS `curl https://github.com/`
  25s 超时，而 `codeload.github.com` 1.02s、`ccr.ccs.tencentyun.com` 0.09s——是 host 级不可达，
  不是间歇性抖动），放在发布关键路径上等于每次发布都赌一次超时。
  改为 **CI 侧打包直传**：`scripts/deploy.sh` + `docker/database/` + `docker/caddy/` +
  `docker-compose.prod.yml` 经 SSH 送到服务器，与 `git checkout` 到同一 commit 等价；
  本次发布的完整 sha 由 CI 写入 `.deploy-commit`，`.deploy-state.commit` 从它取值，
  部署脚本不再依赖服务器上存在 git 仓库。
  镜像链路（构建 → TCR → 生产 pull）**全程境内且稳定**（生产 pull 0.74s），
  未作任何改动——直传只补源码/配置这条断掉的链路

## 6. 实施批次

| 批次 | 内容 | 状态 |
|---|---|---|
| 1 · 本机测试链路 | `scripts/deploy.sh`（staging 模式）+ `docker-compose.ci.yml` + `deploy-staging` job + celery-beat healthcheck | ✅ 已落地并本地全流程演练通过 |
| 2 · 生产链路 | Environment + required reviewers + `DEPLOY_SSH_KEY` / `DEPLOY_KNOWN_HOSTS` + 服务器侧 TCR 凭据 + `deploy-production` job | ✅ 全流程跑通，**2026-11-08 首次生产发布成功**（`main-18f6deb`，详见 §10） |
| 3 · 门禁与治理 | `needs` 补齐 + `db-incremental-guard` + advisory lock + 幂等静态检查 + 三层清理策略 | ✅ 已落地 |
| 4 · 文档 | runbook + README + `.env.example` + CLAUDE.md 发布纪律 | ✅ 已落地 |

## 7. 验证结果

- **本机全流程演练**（staging）：预检 → 迁移（`applied=0, skipped=25`）→ 拉镜像（本地回退）→
  11 个容器全部 healthy（含新增 celery-beat healthcheck）→ `.deploy-state` 落 `status=OK` →
  `.env.bak` 轮转 → 镜像清理 → 退出码 0。bash 5.3 与 macOS 系统 bash 3.2 各跑通一遍
- **回滚演练**：故意用「一启动即退出」的 web 镜像发布 → 换容器失败 →
  自动回滚到上一个 tag 并全部恢复 healthy → `.deploy-state` 落 `status=ROLLED_BACK`，
  `.env` 的 `APP_TAG` 同步退回
- **迁移失败路径**：迁移失败 → 中止且不换容器 → `APP_TAG` 退回上一个版本
  （早期版本此处会留下脏 tag，导致下次回滚目标错位，已修）
- **迁移脚本**：新库应用 → 幂等重放（`applied=0`）→ 故障迁移（表已建但后续语句报错）
  断言事务回滚、台账未污染、失败文件名可定位——三种路径均符合预期
- **增量守卫**：本地复刻 CI 的增量路径（origin/main 的 schema → 增量 → 与从零重放比对）——
  列 1087 / 索引 288 / 约束 301 三张清单完全一致；人为加一列后能检出漂移
- **幂等静态检查**：注入违规迁移文件 → 检查红并精确报出文件与语句；移除后绿
- **静态检查**：`shellcheck -S warning`（两个脚本）干净、`actionlint` 干净、
  `docker compose config` 合并通过

## 8. 明确不做 / 已接受风险

- **不做 GitOps**（ArgoCD / Flux）：单机单 compose 的场景收益低于引入复杂度
- **不在生产机放 runner**：public 仓库 + 生产执行仓库代码 = 直接 RCE 通道
- **CI 内联 ssh 长命令**：不可评审、难回溯，部署逻辑收敛到服务器端一份脚本
- **不做发布前数据库备份**（用户决策）
- **不改生产 redis 鉴权 / 5432 暴露**：独立加固项，本次不动

## 9. 首次生产发布前必须确认

1. **服务器工作树**：CI 已改为直传资产，不再 `git checkout --force` 也不再 `git clean`，
   服务器工作树原样保留、只被同名文件覆盖
   - **已核实（2026-11-07）**：服务器工作树虽脏，但内容与 `origin/main` **逐字节一致**
     （`docker-compose.prod.yml` blob `5aaaf8ce`、`docker/caddy/Caddyfile` blob `bd97e7e4`、
     12 个未跟踪迁移文件 blob 与 main 一致），直传覆盖后线上生效内容与 main 一致
   - 服务器克隆的 refspec 已放宽为 `+refs/heads/*:refs/remotes/origin/*`，
     但发布链路已不依赖它（GitHub 链路不稳）
2. GitHub secret `DEPLOY_SSH_KEY` / `DEPLOY_KNOWN_HOSTS`
   - **已配置（2026-11-07）**：专用 ed25519 密钥对，公钥已装进服务器 `authorized_keys`
     （原 1 条 + 新 1 条）；`known_hosts` 三种密钥类型指纹与服务器 host key 逐一比对一致
3. GitHub Environment `production` 的 required reviewers —— **用户已配置**
4. 生产机 `/root/.docker/config.json` 已有 TCR 凭据（600）
   - **已核实**：文件存在（600），auths 含 `ccr.ccs.tencentyun.com`，与 compose 镜像前缀一致
5. 直传机制已演练：`tar + scp + 解压` 在服务器 `/tmp` 沙箱验证，
   解压出的迁移集与线上现有迁移集 `diff` 完全一致，compose 文件一致，`deploy.sh` 语法通过

## 10. 首次生产发布实录（2026-11-07）

**第一次尝试（merge commit `189f906`）失败在「同步资产」步骤，部署步骤未执行，线上零影响。**

现象：`tar: docker/caddy/Caddyfile: Cannot open: File exists` /
`tar: docker/caddy/Dockerfile: Cannot open: Permission denied`。

根因：远端 `tar -xzf` 以 `ubuntu` 身份执行，而服务器 `/opt/investment/docker/caddy/`
是 **root 属主**（2026-10-16 手工发布时以 root 创建，此后未改属主）。
非 root 无法覆盖 root 属主目录里的文件 → tar 报错退出。
tar 会跳过错误继续解后面的条目，所以 `scripts/deploy.sh`、25 个迁移、compose 事实上已落地，
但 `.deploy-commit` 因 `set -eu` 未写入——**同步是「半套」状态**。

修法（三处）：
1. 远端提取整体改走 `sudo bash -s`（发布本来就要 root 权限执行 deploy.sh）
2. `tar --no-same-owner`：不让归档里的构建机 uid 覆盖服务器属主
   （否则文件会挂上构建机的 uid 501，服务器上不存在该用户）
3. 同步步骤加**资产落地完整性校验**：关键文件缺一即中止，迁移文件数与 CI 侧
   不一致也中止——不让半套资产带着进下一步

验证：修复方案在服务器实测通过（`--- 已同步：迁移 25 个，发布资产齐全 ---`）。
失败后的线上状态已核对：`APP_TAG` 仍为 `main-67efbb7`，11 个容器全部 running。

**第二次尝试（merge commit `18f6deb`）发布成功。**

- 审批：`production` Environment 的 required reviewers（`domonic18`）拦下 job，
  放行后才执行——闸门有效
- 同步：`--- 已同步：迁移 25 个，发布资产齐全 ---`（root 提取 + 落地校验均生效）
- 迁移：`migrate done: applied=0, skipped(already applied)=25` —— **零 schema 变更**
- 发布：`部署成功：main-18f6deb`，耗时 2m15s（含审批后全程）
- 状态：`.deploy-state` = `current_tag=main-18f6deb` / `previous_tag=main-67efbb7` / `status=OK`
- 线上：11 个容器全部 running 且跑 `main-18f6deb`；`https://invest.17aitech.com/health`
  返回 `{"status":"ok","warmup_done":true}`
- 治理：每个仓库保留当前 + 1 个回滚目标（`main-67efbb7` 在手），悬空镜像 0，磁盘剩余 30G，
  `.env.bak` 1 份

## 11. 路线 C：迁移改由独立镜像执行（2026-11-08）

**为什么改**：原先发布时把 `docker/database/` 同步到服务器、由宿主机跑
`bash docker/database/migrate.sh`。这条链路有两个结构性缺陷：
迁移内容与发布代码是两份独立传输的产物，**可能不对齐**（服务器上那份可能不是本次发布的）；
宿主机执行迁移要求生产机有 psql 或可执行 compose 的 psql 兜底路径。

**改法**：迁移文件与 `migrate.sh` 打进**独立 migrate 镜像**，与应用镜像同 tag
（`<branch>-<sha7>`）发布。`deploy.sh` 用
`docker compose run --rm --no-deps --pull never -T migrate` 触发一次迁移，
宿主机不再需要 psql，迁移内容由镜像唯一决定。

**新增资产**：`docker/migrate/Dockerfile`（基础镜像 `postgres:16-alpine`，只为拿 psql 客户端）。

**关键决策**：

| 决策 | 选择 | 理由 |
|---|---|---|
| migrate 服务是否常驻 | `profiles: [migrate]`，`compose up` 不启动 | 迁移是一次性动作，不该占常驻资源；compose 会自动为目标服务启用 profile |
| 迁移镜像是否进 `APP_SERVICES` | **不进**，单独 `pull_migrate_image` | 回滚不跑迁移；若回滚目标没有 migrate 镜像（如路线 C 上线前的老版本），把它塞进通用拉取会让**回滚被迁移镜像的缺失拖垮** |
| 服务器上是否还同步 `docker/database/` | **仍然同步** | 防止宿主机留一份陈旧迁移文件——人工误跑它会静默漏掉新迁移。同步 + 文件数校验保证它与本次发布同 commit |
| 镜像仓库前缀推导 | 改为只认「registry/namespace/repo」三段式 | `docker compose config --images` 是**散列序**，取第一行可能拿到 `timescale/timescaledb`，推出的前缀就错了（此前是运气好） |

**顺带修掉的两个真 bug**：

1. **`migrate.sh` 在 alpine 下必失败**：`mktemp` 模板 `xxx.XXXXXX.sql` —— busybox 的
   mktemp 要求 X 在末尾，GNU/macOS 允许后缀。脚本此前只在宿主机跑过，从未在容器里跑过。
   改为 `migrate-stream.XXXXXX`（无后缀）。
2. **`grep -q` + `pipefail` 的 SIGPIPE 陷阱**：`grep -q` 命中即退出会让上游管道写端吃
   SIGPIPE，`set -o pipefail` 下整条管道返回 141，被误判成失败。`deploy.sh` 里
   `compose config --services | grep -qx migrate` 因此稳定失败。改用不带 `-q` 的
   `grep -x ... >/dev/null`（读完整个输入），`head -n` 同样换成 `sed -n`。

**本机演练结果**（staging 全流程）：

- 正常发布：拉镜像（401 时回退本地同 tag 镜像）→ 迁移镜像跑出 `applied=0, skipped=25`
  → 换容器 → 10 个容器全 healthy → `.deploy-state` status=OK
- 迁移镜像缺失：中止并报「迁移镜像拉取失败」，**未换容器**，`APP_TAG` 已退回
- 迁移内容出错（塞一条坏迁移进镜像）：psql 报错 → 事务回滚（坏表未建、台账未污染）
  → 中止发布，**旧容器继续服务**，`APP_TAG` 已退回
- 镜像内容验证：空库上从零应用 25 条 → 重放全跳过（幂等）
- 无匿名卷泄漏（`docker volume ls` 计数前后都是 7），迁移容器 `--rm` 后无残留

## 12. 路线 C 生产发布实录（2026-11-08）

**第一次尝试（merge commit `24a8acc`）止于 CI 门禁，线上零影响。**
main 流水线在 `Web / 前端` job 红，两次尝试两种原因（均与路线 C 无关，develop 与
PR 流水线此前均通过）：

1. `KnowledgePlayer.test.tsx > resumes from saved localStorage position` 偶发
   `expected +0 to be 42`。起播点落点 `pendingSeekRef` 由 `streamUrl` effect 写入，
   测试在 `video` 元素挂载后立刻派发 `loadedmetadata`——挂载不保证 effect 已执行，
   慢 runner 上 effect 晚于该事件，续播未生效。改法：`renderPlayer` 统一等 `src`
   属性落位（该属性只由该 effect 设置，等它即等价于等 effect 跑完）。
2. 断言全过（568/568）却报 unhandled error `ReferenceError: window is not defined`，
   栈在 react-dom 的 `prepareForCommit`。react-dom 每次 commit 直接读全局 `window`；
   用例跑完、jsdom 环境销毁后队列里未 flush 的更新才执行 → window 已不存在 →
   unhandled error → vitest 退出码非零 → job 红。改法：`setup.ts` 注册 `afterEach`，
   环境销毁前用 `act` + 一个宏任务 tick 把 React scheduler 队列跑空。

两处修复经 PR #165 进 develop、PR #166 进 main，均为**测试侧改动，无生产代码变更**。

**第二次尝试（merge commit `c33c626`）发布成功，路线 C 首次在生产跑通。**

- 闸门：`production` Environment 的 required reviewers 拦下 job，API 放行后才执行
- 同步：`--- 已同步：迁移 25 个，发布资产齐全 ---`（root 提取 + 落地校验生效）
- **迁移走独立镜像**：TCR 拉 `migrate:main-c33c626`（8.7s）→ `compose run --rm
  --no-deps --pull never -T migrate` → `migrate done: applied=0, skipped(already
  applied)=25`——**零 schema 变更**，宿主机无 psql 也能迁移
- 发布：`部署成功：main-c33c626`，耗时约 2 分钟
- 状态：`.deploy-state` = `current_tag=main-c33c626` / `previous_tag=main-18f6deb` /
  `status=OK`；`.env` 的 `APP_TAG` 同值
- 线上：11 个容器全部 running 且跑 `main-c33c626`；
  `https://invest.17aitech.com/health` 返回 `{"status":"ok","warmup_done":true}`
- 治理：每个仓库保留 3 个 tag（当前 + 2 个回滚目标，`main-18f6deb` 与 `main-67efbb7`
  在手），磁盘剩余 30G，`.env.bak` 2 份

**本轮暴露的工程问题（已修，记录备查）**：前端测试有两类独立偶发红，都会让整条
main 流水线红掉、卡住发布。一类是**用例与 effect 的时序竞态**（组件已挂载但 effect
未执行），一类是**环境销毁后残留提交**（断言全过但 vitest 退出码非零）。两者都不是
「重跑就好」的问题——重跑只会掩盖它们。
