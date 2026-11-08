#!/usr/bin/env bash
# ============================================================
# 统一部署脚本 —— CI/CD 的唯一部署入口
#
# 用法：
#   bash scripts/deploy.sh --env staging --tag develop-<sha>
#   sudo bash scripts/deploy.sh --env prod --tag main-<sha>
#   bash scripts/deploy.sh --env staging --gc-only
#
# 流程：参数校验 → 预检 → .env 备份轮转 + 钉 APP_TAG → 拉镜像 → 数据库迁移（先行）→
#       换容器 → 健康检查 → 落 .deploy-state → 失败自动回滚 → 镜像/备份清理
#
# --gc-only：只做镜像回收，不部署。给 CI 一个「与部署成败无关」的清理入口——
#       清理原先只挂在部署成功路径末尾，整栈停用（staging）或部署失败时都不跑，
#       构建机上 CI 加载的镜像便只增不减（2026-11-08 实测：五个仓库各积 7~8 个
#       sha tag，其中 45 小时前的老 tag 一个没删）。
#
# 设计约束（详见 docs/deployment-runbook.md）：
#   - 部署逻辑只有这一份，可评审、可回溯；CI 不内联长命令
#   - 迁移先行：迁移失败则旧版本继续服务，零影响
#   - 迁移由独立 migrate 镜像执行（路线 C）：迁移文件打进镜像，与应用代码同 commit；
#     宿主机不装 psql、不再从外部同步迁移文件
#   - 失败自动回滚到上一个 tag，回滚保留现场（日志不删）
#   - 镜像按仓库分组保留最新 N 个（当前 + N-1 个回滚目标）；
#     只清悬空层，绝不用 docker image prune -a（会删掉回滚目标）
#   - 镜像清理由退出兜底保证：无论成功、失败还是跳过都跑一次。原先只挂在成功路径
#     末尾，「磁盘余量不足 → 预检失败 → 不清理 → 磁盘永远不足」是个闭环
#   - staging 环境整栈未运行（有意停用）时跳过本次部署并以 0 退出，CI 另行标注；
#     prod 无此豁免：环境异常一律硬失败
#
# 依赖：docker + docker compose v2；生产机需 root（docker 组权限不足）
# ============================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

ENV_NAME=""
IMAGE_TAG=""
GC_ONLY=false
KEEP_IMAGES="${DEPLOY_KEEP_IMAGES:-3}"
DISK_MIN_FREE_GB="${DEPLOY_DISK_MIN_FREE_GB:-5}"
HEALTH_TIMEOUT="${DEPLOY_HEALTH_TIMEOUT:-300}"
STATE_FILE="$REPO_ROOT/.deploy-state"
COMMIT_FILE="$REPO_ROOT/.deploy-commit"
LOG_DIR="$REPO_ROOT/.deploy"
ENV_OWNER=""
# 镜像清理的豁免版本列表（当前运行版本 + 回滚目标）：退出兜底的清理要用，
# 部署中途中断时按它们豁免删除
PROTECT_TAGS=""
CLEANUP_DONE=0
# 退出兜底是否可用：豁免版本名单算出来之前不装 trap（否则清理会误删回滚目标）
TRAP_READY=0
REGISTRY="${DEPLOY_REGISTRY:-ccr.ccs.tencentyun.com}"
# 只拉应用镜像：postgres / redis / minio 等基础镜像在境内/离线环境拉不动，
# 且服务器上已有本地副本，pull 它们只会拖慢发布甚至失败
APP_SERVICES="web douyin-signer paper-trade celery-beat celery-worker celery-worker-heavy collector-stream agent-intraday-exec"
log()  { printf '[deploy %s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }
warn() { printf '[deploy %s] WARN: %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >&2; }
fail() { printf '[deploy %s] ERROR: %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >&2; exit 1; }

# 环境整栈未运行时的跳过出口：明确记一笔并以 0 退出，
# 让 CI 把「环境停着、没部署」与「部署成功」区分开，不让绿灯被误读。
skip_deploy() {
    local reason="$1"
    log "=============================================================="
    log "SKIP：本次部署已跳过"
    log "原因：${reason}"
    log "本次未做部署变更：未拉镜像、未执行迁移、未换容器、未改 .env（镜像回收仍会执行）"
    log "如需真正部署，请先拉起该环境的 compose 栈，再重跑本流水线"
    log "=============================================================="
    # 在 CI 里把「跳过」透出给后续步骤（步骤输出可被 job 的其它 step 引用）
    if [ -n "${GITHUB_OUTPUT:-}" ]; then
        printf 'skipped=true\n' >> "$GITHUB_OUTPUT"
    fi
    exit 0
}

usage() {
    cat <<'EOF'
用法: bash scripts/deploy.sh --env <staging|prod> --tag <image-tag>
      bash scripts/deploy.sh --env <staging|prod> --gc-only

  --env   staging = 本机测试环境（docker-compose.yml + docker-compose.ci.yml）
          prod    = 生产环境（docker-compose.prod.yml）
  --tag   staging 期望 develop-<sha>；prod 期望 main-<sha>（短 sha 或完整 sha）
  --gc-only  只做镜像回收，不部署（不带 --tag）。给 CI 一个与部署成败无关的清理入口
EOF
}

# ---------------------------------------------------------------- 参数解析

parse_args() {
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --env) ENV_NAME="${2:-}"; shift 2 ;;
            --tag) IMAGE_TAG="${2:-}"; shift 2 ;;
            --gc-only) GC_ONLY=true; shift ;;
            -h|--help) usage; exit 0 ;;
            *) fail "未知参数：$1（-h 看用法）" ;;
        esac
    done
    [ -n "$ENV_NAME" ] || { usage >&2; fail "缺少 --env"; }
    # --gc-only 只回收镜像不部署，不需要 tag
    [ "$GC_ONLY" = true ] || [ -n "$IMAGE_TAG" ] || { usage >&2; fail "缺少 --tag"; }
}

validate() {
    case "$ENV_NAME" in
        prod)    TAG_RE='^main-[0-9a-f]{7,40}$' ;;
        staging) TAG_RE='^develop-[0-9a-f]{7,40}$' ;;
        *) fail "--env 只能是 prod 或 staging，收到：$ENV_NAME" ;;
    esac
    # tag 同时是镜像引用的一部分，只放行白名单正则，杜绝注入与误传 latest
    # --gc-only 不部署、不引用镜像，无需校验 tag
    if [ "$GC_ONLY" != true ]; then
        echo "$IMAGE_TAG" | grep -Eq "$TAG_RE" \
            || fail "非法镜像 tag：${IMAGE_TAG}（${ENV_NAME} 要求匹配 ${TAG_RE}）"
    fi

    if [ "$ENV_NAME" = "prod" ]; then
        COMPOSE_PATHS=(docker-compose.prod.yml)
        UP_ARGS=(--remove-orphans)
        # caddy 仅生产存在（固定 tag 2，不随 APP_TAG 走）
        APP_SERVICES="$APP_SERVICES caddy"
    else
        COMPOSE_PATHS=(docker-compose.yml docker-compose.ci.yml)
        # staging 不清 orphan：CI 覆盖把 minio 置入 ci-disabled profile，
        # compose 会视其为孤儿并清掉，连带干掉开发者本地正在跑的 minio 容器
        UP_ARGS=()
    fi
    COMPOSE_F=()
    for p in "${COMPOSE_PATHS[@]}"; do COMPOSE_F+=(-f "$p"); done
    # migrate.sh 的 docker 兜底路径靠 COMPOSE_FILE 找回同一个 compose 项目
    COMPOSE_FILE="$(IFS=:; echo "${COMPOSE_PATHS[*]}")"
    export COMPOSE_FILE
}

compose() { docker compose "${COMPOSE_F[@]}" "$@"; }

# ---------------------------------------------------------------- 小工具

stat_owner() {
    stat -c '%u:%g' "$1" 2>/dev/null || stat -f '%u:%g' "$1" 2>/dev/null || echo ""
}

env_get() {
    # 读 .env 的某个键（不做 shell 求值，避免 .env 里的 ${VAR} 被提前展开）
    local key="$1" default="${2:-}" val
    val="$(grep -E "^${key}=" .env 2>/dev/null | tail -n 1 | cut -d= -f2- || true)"
    if [ -n "$val" ]; then printf '%s' "$val"; else printf '%s' "$default"; fi
}

rotate_env_backup() {
    # .env → .env.bak → .env.bak.1 → .env.bak.2（最多 3 份，超出删最旧）
    rm -f .env.bak.2
    [ -f .env.bak.1 ] && mv .env.bak.1 .env.bak.2 || true
    [ -f .env.bak ] && mv .env.bak .env.bak.1 || true
    cp .env .env.bak
}

set_env_var() {
    local key="$1" val="$2" tmp
    tmp="$(mktemp "${TMPDIR:-/tmp}/deploy-env.XXXXXX")"
    if grep -qE "^${key}=" .env 2>/dev/null; then
        awk -v k="$key" -v v="$val" '
            $0 ~ "^"k"=" { print k"="v; next }
            { print }
        ' .env > "$tmp"
    else
        cat .env > "$tmp"
        printf '%s=%s\n' "$key" "$val" >> "$tmp"
    fi
    cat "$tmp" > .env
    rm -f "$tmp"
}

restore_owner() {
    # 生产机以 root 执行本脚本，.env 属主须还原给 ubuntu（否则后续 git/编辑受阻）
    local owner="$1"
    [ -n "$owner" ] || return 0
    chown "$owner" .env .env.bak .env.bak.1 .env.bak.2 2>/dev/null || true
}

restore_prev_tag() {
    # 失败发生在换容器之前：把 APP_TAG 退回上一个版本，保持 .env 与实际运行版本一致
    local prev="$1" owner="$2"
    set_env_var APP_TAG "$prev"
    restore_owner "$owner"
    warn "APP_TAG 已退回 ${prev:-（空）}"
}

# ---------------------------------------------------------------- 预检

preflight() {
    command -v docker >/dev/null 2>&1 || fail "docker 不存在"
    docker compose version >/dev/null 2>&1 || fail "docker compose v2 不可用（需 compose plugin）"
    docker info >/dev/null 2>&1 || fail "无权访问 docker daemon（生产机请用 sudo 执行本脚本）"

    local compose_file
    for compose_file in "${COMPOSE_PATHS[@]}"; do
        [ -f "$compose_file" ] || fail "缺少 compose 文件：$compose_file"
    done
    [ -f .env ] || fail "缺少 .env（部署前须先准备）"
    # 迁移走独立 migrate 镜像：compose 必须定义该服务，否则无从执行迁移
    # grep 不带 -q：-q 命中即退出会让上游吃 SIGPIPE，pipefail 下误判为失败
    compose --profile migrate config --services 2>/dev/null | grep -x migrate >/dev/null \
        || fail "compose 未定义 migrate 服务（迁移镜像路线要求独立的 migrate 服务）"

    # 磁盘余量：Docker Desktop 的 DockerRootDir 在虚拟机内（宿主机无此路径），
    # 此时改看工程目录所在卷（workspace/ 数据与镜像都在这一侧增长）
    local root free_gb disk_path="$REPO_ROOT"
    root="$(docker info --format '{{.DockerRootDir}}' 2>/dev/null || true)"
    [ -n "$root" ] && [ -d "$root" ] && disk_path="$root"
    free_gb="$(df -Pk "$disk_path" | awk 'NR==2 {printf "%d", $4/1048576}')"
    if [ "${free_gb:-0}" -lt "$DISK_MIN_FREE_GB" ]; then
        fail "磁盘剩余 ${free_gb}G < 阈值 ${DISK_MIN_FREE_GB}G（${disk_path}），先清理磁盘"
    fi
    log "预检通过：磁盘剩余 ${free_gb}G（${disk_path}），compose=$COMPOSE_FILE"

    local pg_id pg_health running_any
    pg_id="$(compose ps -q postgres 2>/dev/null || true)"
    if [ -z "$pg_id" ]; then
        # postgres 没跑。区分两种情形：
        #   ①整栈都没跑 —— 环境被有意停用（测试环境已按决策停用），跳过本次部署
        #   ②栈还在但 postgres 掉了 —— 真的故障，必须硬失败，不能拿「跳过」盖住
        running_any="$(compose ps -q 2>/dev/null || true)"
        if [ "$ENV_NAME" = "staging" ] && [ -z "$running_any" ]; then
            skip_deploy "本机测试环境整栈未运行（无任何容器在跑，postgres 未启动）"
        fi
        fail "postgres 容器未运行（先执行 compose up -d postgres --wait）"
    fi
    pg_health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$pg_id")"
    [ "$pg_health" = "healthy" ] || [ "$pg_health" = "running" ] \
        || fail "postgres 未就绪：$pg_health"
}

# --gc-only 的预检：只要求能算镜像坐标与能读 .env，不碰容器
preflight_gc() {
    command -v docker >/dev/null 2>&1 || fail "docker 不存在"
    docker compose version >/dev/null 2>&1 || fail "docker compose v2 不可用（需 compose plugin）"
    docker info >/dev/null 2>&1 || fail "无权访问 docker daemon（生产机请用 sudo 执行本脚本）"

    # compose 文件只用于「推导命名空间」的可选比对，缺失不阻断：
    # CI 显式传 DEPLOY_NAMESPACE 时镜像坐标不依赖 compose，清理照样能跑
    # （构建机上 compose 未必常驻——它由 deploy-staging 同步，main 推送时那个 job 不跑）
    local compose_file
    for compose_file in "${COMPOSE_PATHS[@]}"; do
        [ -f "$compose_file" ] || warn "缺少 compose 文件：${compose_file}（镜像坐标改由显式命名空间决定）"
    done
    # .env 与 .deploy-state 至少要有一个：豁免名单（当前运行版本 + 回滚目标）靠它们，
    # 两个都没有就无从保护正在跑的镜像，此时宁可不清理
    if [ ! -f .env ] && [ ! -f "$STATE_FILE" ]; then
        fail "缺少 .env 与 .deploy-state（无从判定当前运行版本，清理会失去豁免保护）"
    fi
    [ -f .env ] || warn "缺少 .env（当前运行版本改从 $STATE_FILE 判定）"
    log "GC 预检通过：compose=$COMPOSE_FILE"
}

# ---------------------------------------------------------------- 迁移
run_migrations() {
    # 迁移走独立 migrate 镜像（路线 C）：镜像内的迁移文件与本次发布的代码同 commit，
    # 宿主机不再需要 psql，也不再依赖外部同步过来的迁移文件。
    # --no-deps：postgres 已在跑（预检已确认健康），不让 compose 再动它
    # --pull never：镜像已在 pull_migrate_image 阶段拉好，现场绝不联网拉取
    # -T：非交互（CI / SSH）下不分配 TTY
    log "执行数据库迁移（独立 migrate 镜像，先行，失败即中止，旧版本继续服务）"
    compose run --rm --no-deps --pull never -T migrate
}

# ---------------------------------------------------------------- 健康检查

wait_healthy() {
    local timeout="$1" deadline bad name running health
    deadline=$(( $(date +%s) + timeout ))
    while :; do
        bad=""
        for cid in $(compose ps -q --all 2>/dev/null); do
            name="$(docker inspect -f '{{.Name}}' "$cid" 2>/dev/null | sed 's|^/||')"
            running="$(docker inspect -f '{{.State.Running}}' "$cid" 2>/dev/null || echo unknown)"
            health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$cid" 2>/dev/null || echo unknown)"
            if [ "$running" != "true" ]; then
                bad="$bad ${name}(running=$running)"
            elif [ "$health" != "none" ] && [ "$health" != "healthy" ]; then
                bad="$bad ${name}(health=$health)"
            fi
        done
        [ -z "$bad" ] && return 0
        if [ "$(date +%s)" -ge "$deadline" ]; then
            warn "超时 ${timeout}s 仍未健康：$bad"
            return 1
        fi
        sleep 5
    done
}

# ---------------------------------------------------------------- 状态与回滚

read_state_field() {
    [ -f "$STATE_FILE" ] || return 0
    grep -E "^$1=" "$STATE_FILE" | tail -n 1 | cut -d= -f2- || true
}

# 当前正在运行的版本：.env 的 APP_TAG → .env.bak 的 → 状态文件的 current_tag。
# 状态文件里 current_tag 才是「正在跑的版本」——previous_tag 是上一次发布前的版本，
# 退过去等于连跳两级
current_running_tag() {
    local tag
    tag="$(env_get APP_TAG '')"
    [ -n "$tag" ] || tag="$(grep -E '^APP_TAG=' .env.bak 2>/dev/null | tail -n 1 | cut -d= -f2- || true)"
    [ -n "$tag" ] || tag="$(read_state_field current_tag)"
    printf '%s' "$tag"
}

# 清理豁免名单：当前运行版本 + 回滚目标（状态文件里的上一个版本）
protect_tags() {
    printf '%s' "$(current_running_tag) $(read_state_field previous_tag)"
}

resolve_commit() {
    # 本次发布的 commit：CI 同步时落盘的 .deploy-commit 最准（服务器可能没有 git 仓库）；
    # 其次用 tag 里的 sha 反查本地 git；最后退化为 tag 的 sha 片段
    local tag="$1" sha
    sha="${tag#*-}"
    if [ -f "$COMMIT_FILE" ]; then
        cat "$COMMIT_FILE"
        return 0
    fi
    git rev-parse --verify "$sha" 2>/dev/null || echo "$sha"
}

write_state() {
    local status="$1" current="$2" previous="$3" commit="$4"
    cat > "$STATE_FILE" <<EOF
current_tag=$current
previous_tag=$previous
commit=$commit
deployed_at=$(date '+%Y-%m-%dT%H:%M:%S%z')
status=$status
EOF
}

rollback_to() {
    local prev="$1" prev_commit="$2"
    if [ -z "$prev" ]; then
        warn "没有可回滚的版本（.env.bak 中无 APP_TAG），保持现场等待人工处理"
        return 1
    fi
    [ -n "$prev_commit" ] || prev_commit="${prev#*-}"
    warn "开始回滚到 $prev"
    set_env_var APP_TAG "$prev"
    restore_owner "$ENV_OWNER"
    if pull_images >/dev/null 2>&1 && compose up -d --wait ${UP_ARGS[@]+"${UP_ARGS[@]}"} --no-build --pull never >/dev/null 2>&1; then
        if wait_healthy 180; then
            warn "回滚成功：当前运行 $prev"
            write_state ROLLED_BACK "$prev" "" "$prev_commit"
            return 0
        fi
    fi
    warn "回滚失败，需人工介入"
    write_state FAILED_ROLLED_BACK_FAILED "$prev" "" "$prev_commit"
    return 1
}

# ---------------------------------------------------------------- 镜像拉取与清理

# 镜像仓库前缀（registry/namespace），如 ccr.ccs.tencentyun.com/domonic18。
# docker images 的过滤参数按**完整仓库名**匹配，只给短前缀匹配不到、且静默返回空——
# 过滤落空会让清理整段空转，故前缀必须是 registry/namespace 两段完整值。
# compose 推导：config --images 的输出顺序是散列序不能取第一行，但只认
#       「registry/namespace/repo」三段式后，三方镜像（timescale/timescaledb、
#       redis、minio）都不符合，剩下的是本项目自有镜像。
image_prefix() {
    # 优先用显式传入的命名空间（CI 侧由 secret 注入）：compose 推导依赖
    # config --images 的输出顺序（散列序），compose 文件一改就可能推错。
    if [ -n "${DEPLOY_NAMESPACE:-}" ]; then
        local declared composed
        declared="$REGISTRY/$DEPLOY_NAMESPACE"
        composed="$(compose_image_prefix)"
        if [ -n "$composed" ] && [ "$composed" != "$declared" ]; then
            warn "镜像命名空间不一致：显式 $declared 与 compose 推导 $composed 不符，以显式值为准"
        fi
        printf '%s' "$declared"
        return 0
    fi
    compose_image_prefix
}

compose_image_prefix() {
    { compose config --images 2>/dev/null \
        | grep -E '^[^/]+/[^/]+/[^/]+:' | sed -n '1p' | sed -E 's|/[^/]+:[^/:]+$||' || true; }
}

# 判断某个词是否在以空白分隔的列表里
in_list() {
    local needle="$1" list="$2" item
    for item in $list; do
        [ "$item" = "$needle" ] && return 0
    done
    return 1
}

# 服务名 → 镜像仓库名（celery-* 与 collector-stream 共用 collector 镜像）
service_repo() {
    case "$1" in
        celery-*|collector-stream|agent-intraday-exec) echo "collector" ;;
        *) echo "$1" ;;
    esac
}

pull_images() {
    # sha 短 tag 不可变：拉取失败但本地已有同 tag 镜像时继续走（回滚场景下仓库不可达）
    local svc repo prefix failed=""
    prefix="$(image_prefix)"
    for svc in $APP_SERVICES; do
        repo="$(service_repo "$svc")"
        if compose pull "$svc"; then
            continue
        fi
        if [ -n "$prefix" ] && docker image inspect "$prefix/$repo:$IMAGE_TAG" >/dev/null 2>&1; then
            warn "$svc 拉取失败，本地已有 $prefix/$repo:${IMAGE_TAG}，继续"
        else
            failed="$failed $svc"
        fi
    done
    [ -z "$failed" ] || { warn "镜像拉取失败且本地无对应镜像：$failed"; return 1; }
    return 0
}

pull_migrate_image() {
    # 迁移镜像必须先到位：迁移由它执行，拉不到就没法迁移。
    # 单独于 pull_images：回滚不跑迁移，不该被 migrate 镜像的拉取结果拖累。
    local prefix
    if compose pull migrate; then
        return 0
    fi
    prefix="$(image_prefix)"
    if [ -n "$prefix" ] && docker image inspect "$prefix/migrate:$IMAGE_TAG" >/dev/null 2>&1; then
        warn "migrate 镜像拉取失败，本地已有 $prefix/migrate:${IMAGE_TAG}，继续"
        return 0
    fi
    warn "迁移镜像拉取失败且本地无对应镜像"
    return 1
}

# 清理对象：compose 里实际配置的自有镜像仓库 ∪ 服务名映射出来的仓库。
# compose 是权威来源（新增服务改了 compose 立刻可见），服务名映射是补充
# （migrate 在 profile 里，config --images 不含它）。
cleanup_repo_list() {
    local prefix="$1" compose_repos mapped_repos repo extra=""
    [ -n "$prefix" ] || return 0
    # 每段管道都收 || true：pipefail 下 grep 未命中返回 1，会让整个脚本直接退出——
    # 恰恰发生在「过滤落空」这个最该报警、而不是该崩掉的场景
    compose_repos="$(compose --profile migrate config --images 2>/dev/null \
        | grep -F "$prefix/" | awk -F/ '{print $3}' | cut -d: -f1 | sort -u | tr '\n' ' ' || true)"
    mapped_repos="$({ for svc in $APP_SERVICES; do service_repo "$svc"; done; echo migrate; } | sort -u | tr '\n' ' ')"
    # compose 里有、映射表里没有 → 映射表漏改，报警而非静默放过
    for repo in $compose_repos; do
        in_list "$repo" "$mapped_repos" || extra="$extra $repo"
    done
    [ -n "$extra" ] && warn "compose 里的自有镜像仓库未被清理清单覆盖：${extra}（service_repo 映射漏改？）"
    printf '%s\n' "$compose_repos $mapped_repos" | tr ' ' '\n' | grep -v '^$' | sort -u | tr '\n' ' ' || true
}

# 只回收镜像，不部署。给 CI 一个与部署成败无关的清理入口：
# 构建机（Mac mini）上 CI 把镜像 load 进本地 docker，部署脚本在那台机上只管
# 部署，不管清理——清理只挂在部署成功路径末尾时，镜像只增不减。
gc_images() {
    local protect
    protect="$(protect_tags)"
    log "镜像回收：豁免版本 ${protect:-（无）}"
    cleanup_images "$protect"
    CLEANUP_DONE=1
}

# cleanup_images <豁免版本列表>
# 列表里的 tag 永不删除（当前运行版本 + 回滚目标）；其余按仓库保留最新 N 个。
cleanup_images() {
    local protect="$1" prefix repos repo tags i
    local removed=0 freed=0 size missing="" listing latest=""
    prefix="$(image_prefix)"
    [ -n "$prefix" ] || { warn "无法推导镜像仓库前缀，跳过镜像清理"; return 0; }
    repos="$(cleanup_repo_list "$prefix")"

    for repo in $repos; do
        # 一次 docker images 拿全：既要判「本地有没有这个仓库」，也要排 sha 版本 tag。
        # 区分两种空：一条都没有 = 过滤落空（路径写错）；有镜像但无 sha tag = 正常跳过
        listing="$(docker images --format '{{.Repository}}\t{{.Tag}}\t{{.CreatedAt}}' "$prefix/$repo" 2>/dev/null || true)"
        if [ -z "$listing" ]; then
            missing="$missing $prefix/$repo"
            continue
        fi
        # latest 是项目明令禁推的可变标签（会被回滚目标顶掉），它既不匹配 sha 版本
        # 规则、也就不计入保留额度与清理范围——只报不改，删不删由人定
        if printf '%s\n' "$listing" | awk -F'\t' '$2 == "latest" {found=1} END {exit found?0:1}'; then
            latest="$latest $prefix/$repo:latest"
        fi
        tags="$(printf '%s\n' "$listing" \
            | awk -F'\t' '$2 ~ /^(main|develop)-[0-9a-f]{7,40}$/' \
            | sort -k3 -r | cut -f2)"
        [ -n "$tags" ] || { log "  ${repo}：本地无 sha 版本镜像，跳过"; continue; }
        i=0
        for t in $tags; do
            i=$((i + 1))
            if [ "$i" -gt "$KEEP_IMAGES" ] && ! in_list "$t" "$protect"; then
                size="$(docker image inspect --format '{{.Size}}' "$prefix/$repo:$t" 2>/dev/null || echo 0)"
                if docker image rm "$prefix/$repo:$t" >/dev/null 2>&1; then
                    removed=$((removed + 1))
                    freed=$((freed + size))
                else
                    warn "镜像删除失败（可能被容器引用）：$prefix/$repo:$t"
                fi
            fi
        done
    done
    # 一个仓库都没有 → 过滤落空：多半是仓库路径不对，旧镜像不会被清理，必须报警
    [ -n "$missing" ] && warn "镜像清理过滤未命中（本地无这些仓库的镜像，仓库路径可能写错）：$missing"
    [ -n "$latest" ] && warn "发现 latest 标签镜像（项目禁用 latest 推送，未自动清理）：$latest"
    # 只清悬空层：docker image prune -a 会连回滚目标一起删掉
    docker image prune -f >/dev/null 2>&1 || true
    log "镜像清理完成：删除 $removed 个镜像，镜像体积合计约 $((freed / 1024 / 1024)) MB（每仓库保留最新 $KEEP_IMAGES 个）"
}

prune_backups() {
    #（head -n -N 在 BSD head 上不支持，改用计数 + sed 取前 N 行；
    #  不用 head：head 提前退出会让上游吃 SIGPIPE，pipefail 下误判为失败）
    local files count
    files="$(ls -1 .env.bak* 2>/dev/null | sort || true)"
    count="$(printf '%s' "$files" | grep -c . || true)"
    if [ "${count:-0}" -gt 3 ]; then
        printf '%s\n' "$files" | sed -n "1,$((count - 3))p" | while read -r f; do
            rm -f "$f"
        done
    fi
    if [ -d "$LOG_DIR" ]; then
        ls -1t "$LOG_DIR"/*.log 2>/dev/null | tail -n +11 | while read -r f; do
            rm -f "$f"
        done
    fi
}

# ---------------------------------------------------------------- 退出兜底

# 镜像清理由退出兜底保证：无论成功、失败还是跳过都跑一次。
# 原先清理只挂在成功路径末尾——staging 整栈停用（skip_deploy 直接 exit 0）
# 或部署失败（fail 直接 exit 1）都不跑，构建机上 CI 加载的镜像只增不减：
# 「磁盘余量不足 → 预检失败 → 不清理 → 磁盘永远不足」是个闭环。
on_exit() {
    local rc=$?
    trap - EXIT
    if [ "$CLEANUP_DONE" -eq 1 ] || [ "$TRAP_READY" -eq 0 ]; then
        exit $rc
    fi
    cleanup_images "$PROTECT_TAGS" || true
    exit $rc
}

# ---------------------------------------------------------------- 主流程

main() {
    parse_args "$@"
    validate

    if [ "$GC_ONLY" = true ]; then
        # 只回收镜像：不部署、不碰 .env、不碰容器。
        # 给 CI 一个与部署成败无关的清理入口（构建机上 CI 加载的镜像堆积）。
        preflight_gc
        gc_images
        return 0
    fi

    local owner previous commit prev_commit
    # 豁免名单先算出来：退出兜底要靠它保护「当前运行版本」与「回滚目标」。
    # 必须在 preflight 之前——staging 整栈停用时 skip_deploy 在 preflight 里
    # 直接 exit 0，那正是清理最该跑到的路径。
    # 上一个版本 = 当前正在运行的版本（回滚要退到它）
    previous="$(current_running_tag)"
    # 豁免 = 当前运行版本 + 回滚目标 + 本次发布的新版本
    # 新版本从一开始就进豁免：它已经被拉下来，删了这次发布就白拉；
    # 换容器成功或失败都不影响它免于清理
    PROTECT_TAGS="$(protect_tags) $IMAGE_TAG"
    TRAP_READY=1
    trap on_exit EXIT

    preflight

    owner="$(stat_owner .env)"
    ENV_OWNER="$owner"
    # 上一个版本的 commit = 旧状态文件里的 commit（本次发布覆盖前先取出来）
    prev_commit="$(read_state_field commit)"
    commit="$(resolve_commit "$IMAGE_TAG")"

    rotate_env_backup
    set_env_var APP_TAG "$IMAGE_TAG"
    restore_owner "$owner"
    log "APP_TAG 钉为 ${IMAGE_TAG}（上一个版本：${previous:-无}）"

    # 拉镜像 / 迁移阶段失败时还没换容器，必须把 APP_TAG 退回上一个版本——
    # 否则 .env 会指向一个从未跑起来的 tag，下一次部署的回滚目标就错了
    if ! pull_images; then
        restore_prev_tag "$previous" "$owner"
        fail "镜像拉取失败：$IMAGE_TAG"
    fi

    if ! pull_migrate_image; then
        restore_prev_tag "$previous" "$owner"
        fail "迁移镜像拉取失败：$IMAGE_TAG"
    fi

    if ! run_migrations; then
        restore_prev_tag "$previous" "$owner"
        fail "数据库迁移失败：已中止发布，旧版本继续服务（未换容器）"
    fi

    if ! compose up -d --wait ${UP_ARGS[@]+"${UP_ARGS[@]}"} --no-build --pull never; then
        warn "容器更新失败"
        write_state FAILED "$IMAGE_TAG" "$previous" "$commit"
        rollback_to "$previous" "$prev_commit" || true
        fail "部署失败，已尝试回滚"
    fi

    # 换容器已成功：新版本正在跑（它从一开始就进了豁免名单，这里不再重复追加）

    if ! wait_healthy "$HEALTH_TIMEOUT"; then
        warn "健康检查未通过"
        write_state FAILED "$IMAGE_TAG" "$previous" "$commit"
        rollback_to "$previous" "$prev_commit" || true
        fail "部署失败（健康检查未通过），已尝试回滚"
    fi

    write_state OK "$IMAGE_TAG" "$previous" "$commit"
    log "部署成功：${IMAGE_TAG}（commit ${commit}）"

    cleanup_images "$PROTECT_TAGS" || true
    CLEANUP_DONE=1
    prune_backups
    log "完成"
}

main "$@"
