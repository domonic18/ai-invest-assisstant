#!/usr/bin/env bash
# ============================================================
# 统一部署脚本 —— CI/CD 的唯一部署入口
#
# 用法：
#   bash scripts/deploy.sh --env staging --tag develop-<sha>
#   sudo bash scripts/deploy.sh --env prod --tag main-<sha>
#
# 流程：参数校验 → 预检 → .env 备份轮转 + 钉 APP_TAG → 数据库迁移（先行）→
#       换容器 → 健康检查 → 落 .deploy-state → 失败自动回滚 → 镜像/备份清理
#
# 设计约束（详见 docs/deployment-runbook.md）：
#   - 部署逻辑只有这一份，可评审、可回溯；CI 不内联长命令
#   - 迁移先行：迁移失败则旧版本继续服务，零影响
#   - 失败自动回滚到上一个 tag，回滚保留现场（日志不删）
#   - 镜像按仓库分组保留最新 N 个（当前 + N-1 个回滚目标）；
#     只清悬空层，绝不用 docker image prune -a（会删掉回滚目标）
#
# 依赖：docker + docker compose v2；生产机需 root（docker 组权限不足）
# ============================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

ENV_NAME=""
IMAGE_TAG=""
KEEP_IMAGES="${DEPLOY_KEEP_IMAGES:-3}"
DISK_MIN_FREE_GB="${DEPLOY_DISK_MIN_FREE_GB:-5}"
HEALTH_TIMEOUT="${DEPLOY_HEALTH_TIMEOUT:-300}"
STATE_FILE="$REPO_ROOT/.deploy-state"
COMMIT_FILE="$REPO_ROOT/.deploy-commit"
LOG_DIR="$REPO_ROOT/.deploy"
ENV_OWNER=""
# 只拉应用镜像：postgres / redis / minio 等基础镜像在境内/离线环境拉不动，
# 且服务器上已有本地副本，pull 它们只会拖慢发布甚至失败
APP_SERVICES="web douyin-signer paper-trade celery-beat celery-worker celery-worker-heavy collector-stream agent-intraday-exec"
log()  { printf '[deploy %s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }
warn() { printf '[deploy %s] WARN: %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >&2; }
fail() { printf '[deploy %s] ERROR: %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >&2; exit 1; }

usage() {
    cat <<'EOF'
用法: bash scripts/deploy.sh --env <staging|prod> --tag <image-tag>

  --env   staging = 本机测试环境（docker-compose.yml + docker-compose.ci.yml）
          prod    = 生产环境（docker-compose.prod.yml）
  --tag   staging 期望 develop-<sha>；prod 期望 main-<sha>（短 sha 或完整 sha）
EOF
}

# ---------------------------------------------------------------- 参数解析

parse_args() {
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --env) ENV_NAME="${2:-}"; shift 2 ;;
            --tag) IMAGE_TAG="${2:-}"; shift 2 ;;
            -h|--help) usage; exit 0 ;;
            *) fail "未知参数：$1（-h 看用法）" ;;
        esac
    done
    [ -n "$ENV_NAME" ] || { usage >&2; fail "缺少 --env"; }
    [ -n "$IMAGE_TAG" ] || { usage >&2; fail "缺少 --tag"; }
}

validate() {
    case "$ENV_NAME" in
        prod)    TAG_RE='^main-[0-9a-f]{7,40}$' ;;
        staging) TAG_RE='^develop-[0-9a-f]{7,40}$' ;;
        *) fail "--env 只能是 prod 或 staging，收到：$ENV_NAME" ;;
    esac
    # tag 同时是镜像引用的一部分，只放行白名单正则，杜绝注入与误传 latest
    echo "$IMAGE_TAG" | grep -Eq "$TAG_RE" \
        || fail "非法镜像 tag：${IMAGE_TAG}（${ENV_NAME} 要求匹配 ${TAG_RE}）"

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
    [ -f docker/database/migrate.sh ] || fail "缺少 docker/database/migrate.sh"

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

    local pg_id pg_health
    pg_id="$(compose ps -q postgres 2>/dev/null || true)"
    [ -n "$pg_id" ] || fail "postgres 容器未运行（先执行 compose up -d postgres --wait）"
    pg_health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$pg_id")"
    [ "$pg_health" = "healthy" ] || [ "$pg_health" = "running" ] \
        || fail "postgres 未就绪：$pg_health"
}

# ---------------------------------------------------------------- 迁移

run_migrations() {
    PGDATABASE="$(env_get POSTGRES_DB invest)"
    PGUSER="$(env_get POSTGRES_USER postgres)"
    PGPASSWORD="$(env_get POSTGRES_PASSWORD '')"
    PGHOST=127.0.0.1
    PGPORT="$(env_get POSTGRES_PORT 5432)"
    export PGDATABASE PGUSER PGPASSWORD PGHOST PGPORT
    log "执行数据库迁移（先行，失败即中止，旧版本继续服务）"
    bash docker/database/migrate.sh
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

# 镜像仓库前缀（如 ccr.ccs.tencentyun.com/domonic18）从 compose 推导，
# 避免脚本里再写一份镜像地址
image_prefix() {
    docker compose "${COMPOSE_F[@]}" config --images 2>/dev/null \
        | head -n 1 | sed -E 's|/[^/]+:[^/:]+$||'
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

cleanup_images() {
    local current_tag="$1" protect_tag="$2" prefix repos repo tags keep_tag i
    prefix="$(image_prefix)"
    [ -n "$prefix" ] || { warn "无法推导镜像仓库前缀，跳过镜像清理"; return 0; }
    repos="$(docker compose "${COMPOSE_F[@]}" config --images 2>/dev/null \
        | sed -E 's|.*/||; s|:.*||' | sort -u)"

    keep_tag="$current_tag"
    for repo in $repos; do
        tags="$(docker images --format '{{.Tag}}\t{{.CreatedAt}}' "$prefix/$repo" 2>/dev/null \
            | awk -F'\t' '$1 ~ /^(main|develop)-[0-9a-f]{7,40}$/' \
            | sort -k2 -r | cut -f1)"
        [ -n "$tags" ] || continue
        i=0
        for t in $tags; do
            i=$((i + 1))
            # 当前版本与上一个版本（回滚目标）永不删除
            if [ "$i" -gt "$KEEP_IMAGES" ] && [ "$t" != "$keep_tag" ] && [ "$t" != "$protect_tag" ]; then
                docker image rm "$prefix/$repo:$t" >/dev/null 2>&1 \
                    || warn "镜像删除失败（可能被容器引用）：$prefix/$repo:$t"
            fi
        done
    done
    # 只清悬空层：docker image prune -a 会连回滚目标一起删掉
    docker image prune -f >/dev/null 2>&1 || true
    log "镜像清理完成（每仓库保留最新 $KEEP_IMAGES 个）"
}

prune_backups() {
    # .env.bak 已由 rotate_env_backup 限死 3 份，这里兜底清理历史遗留
    #（head -n -N 在 BSD head 上不支持，改用计数 + 正数行数）
    local files count
    files="$(ls -1 .env.bak* 2>/dev/null | sort || true)"
    count="$(printf '%s' "$files" | grep -c . || true)"
    if [ "${count:-0}" -gt 3 ]; then
        printf '%s\n' "$files" | head -n $((count - 3)) | while read -r f; do
            rm -f "$f"
        done
    fi
    if [ -d "$LOG_DIR" ]; then
        ls -1t "$LOG_DIR"/*.log 2>/dev/null | tail -n +11 | while read -r f; do
            rm -f "$f"
        done
    fi
}

# ---------------------------------------------------------------- 主流程

main() {
    parse_args "$@"
    validate
    preflight

    local owner previous commit prev_commit
    owner="$(stat_owner .env)"
    ENV_OWNER="$owner"
    # 上一个版本 = 当前 .env 里的 APP_TAG（改之前）；空则退到 .env.bak / 状态文件
    previous="$(env_get APP_TAG '')"
    [ -n "$previous" ] || previous="$(grep -E '^APP_TAG=' .env.bak 2>/dev/null | tail -n 1 | cut -d= -f2- || true)"
    [ -n "$previous" ] || previous="$(read_state_field previous_tag)"
    # 上一个版本的 commit = 旧状态文件里的 commit（本次发布覆盖前先取出来）
    prev_commit="$(read_state_field commit)"
    commit="$(resolve_commit "$IMAGE_TAG")"

    rotate_env_backup
    set_env_var APP_TAG "$IMAGE_TAG"
    restore_owner "$owner"
    log "APP_TAG 钉为 ${IMAGE_TAG}（上一个版本：${previous:-无}）"

    # 迁移 / 拉镜像阶段失败时还没换容器，必须把 APP_TAG 退回上一个版本——
    # 否则 .env 会指向一个从未跑起来的 tag，下一次部署的回滚目标就错了
    if ! run_migrations; then
        restore_prev_tag "$previous" "$owner"
        fail "数据库迁移失败：已中止发布，旧版本继续服务（未换容器）"
    fi

    if ! pull_images; then
        restore_prev_tag "$previous" "$owner"
        fail "镜像拉取失败：$IMAGE_TAG"
    fi

    if ! compose up -d --wait ${UP_ARGS[@]+"${UP_ARGS[@]}"} --no-build --pull never; then
        warn "容器更新失败"
        write_state FAILED "$IMAGE_TAG" "$previous" "$commit"
        rollback_to "$previous" "$prev_commit" || true
        fail "部署失败，已尝试回滚"
    fi

    if ! wait_healthy "$HEALTH_TIMEOUT"; then
        warn "健康检查未通过"
        write_state FAILED "$IMAGE_TAG" "$previous" "$commit"
        rollback_to "$previous" "$prev_commit" || true
        fail "部署失败（健康检查未通过），已尝试回滚"
    fi

    write_state OK "$IMAGE_TAG" "$previous" "$commit"
    log "部署成功：${IMAGE_TAG}（commit ${commit}）"

    cleanup_images "$IMAGE_TAG" "$previous"
    prune_backups
    log "完成"
}

main "$@"
