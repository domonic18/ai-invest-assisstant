#!/usr/bin/env bash
# ============================================================
# 数据库迁移 runner：台账制（exactly-once），新装 / 存量 / 升级共用一条路径
#
# 用法（手动；postgres 起健康后、起应用前执行一次）：
#   bash docker/database/migrate.sh
#
#   宿主机有 psql 时直连（libpq 标准环境变量）：
#     PGHOST=localhost PGUSER=postgres PGPASSWORD=... PGDATABASE=invest bash docker/database/migrate.sh
#   宿主机无 psql 时自动经 `docker compose exec postgres psql` 执行，无需本地安装。
#
# 约定（见 CLAUDE.md「数据库迁移规范」）：
#   - migrations/ 下按文件名排序执行；legacy/ 子目录为历史归档，永不执行
#   - 台账表 schema_migrations 记录已应用迁移，每迁移与其登记同事务提交
#   - 迁移 forward-only：合并后禁止修改；破坏性变更走 expand-contract
#
# 并发：全程在单个 psql 会话内执行，会话首句取会话级 advisory lock——
#       并发部署会排队而不是同时改 schema；脚本退出（含失败）自动释放。
# ============================================================
set -euo pipefail
export LC_ALL=C

: "${PGDATABASE:?PGDATABASE is required (e.g. invest)}"
: "${PGUSER:?PGUSER is required}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIGRATIONS_DIR="${MIGRATIONS_DIR:-$SCRIPT_DIR/migrations}"

# 全局迁移锁键：任意固定常量即可，跨仓库不冲突即可
LOCK_KEY=8261100611
# 取锁等待上限（秒）：只约束「等待」，不约束迁移本身的执行时长
LOCK_WAIT_SECONDS=300

# --- psql 调用方式二选一：宿主机直连 / postgres 容器 exec ---
if command -v psql >/dev/null 2>&1; then
    PGHOST="${PGHOST:-localhost}"
    psql_run() { psql -v ON_ERROR_STOP=1 -q -X -h "$PGHOST" -U "$PGUSER" -d "$PGDATABASE" -f "$1"; }
else
    command -v docker >/dev/null 2>&1 \
        || { echo "ERROR: 宿主机既无 psql 也无 docker，无法执行迁移" >&2; exit 1; }
    docker compose exec -T postgres pg_isready -U "$PGUSER" -d "$PGDATABASE" >/dev/null 2>&1 \
        || { echo "ERROR: postgres 容器未运行或未就绪，先执行 docker compose up -d postgres 并等健康" >&2; exit 1; }
    psql_run() { docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -q -X \
        -U "$PGUSER" -d "$PGDATABASE" -f - < "$1"; }
fi

# 模板必须以 X 结尾：alpine（busybox）的 mktemp 不接受 X 之后还有后缀的形式
STREAM_FILE="$(mktemp "${TMPDIR:-/tmp}/migrate-stream.XXXXXX")"
LOG_FILE="$(mktemp "${TMPDIR:-/tmp}/migrate-log.XXXXXX")"
cleanup() { rm -f "$STREAM_FILE" "$LOG_FILE"; }
trap cleanup EXIT

# --- 生成单会话迁移脚本 ---
# 每个迁移各自 BEGIN/COMMIT：迁移 SQL 与台账登记同事务，失败一起回滚；
# 「是否已应用」的判定也放在锁内的同一会话里做，避免并发读到陈旧台账。
{
    printf 'SET lock_timeout = %s;\n' "'${LOCK_WAIT_SECONDS}s'"
    printf 'SELECT pg_advisory_lock(%s);\n' "$LOCK_KEY"
    printf 'CREATE TABLE IF NOT EXISTS schema_migrations (\n'
    printf '    name        TEXT PRIMARY KEY,\n'
    printf '    applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()\n'
    printf ');\n'

    idx=0
    for f in "$MIGRATIONS_DIR"/*.sql; do
        [ -e "$f" ] || continue
        name="$(basename "$f")"
        idx=$((idx + 1))
        # 文件名白名单：防注入，也防误放杂文件
        if ! grep -qxE '[A-Za-z0-9._-]+' <<<"$name"; then
            echo "ERROR: 非法迁移文件名，拒绝执行：$name" >&2
            exit 1
        fi
        var="m_present_${idx}"
        printf "SELECT count(*) AS %s FROM schema_migrations WHERE name = '%s' \\gset\n" "$var" "$name"
        printf '\\if :%s\n' "$var"
        printf '\\echo skipped: %s\n' "$name"
        printf '\\else\n'
        printf '\\echo applying: %s\n' "$name"
        printf 'BEGIN;\n'
        cat "$f"
        printf '\nINSERT INTO schema_migrations(name) VALUES (%s);\n' "'$name'"
        printf 'COMMIT;\n'
        printf '\\endif\n'
    done

    printf 'SELECT pg_advisory_unlock(%s);\n' "$LOCK_KEY"
} > "$STREAM_FILE"

if ! psql_run "$STREAM_FILE" > "$LOG_FILE" 2>&1; then
    failed="$(grep '^applying: ' "$LOG_FILE" | tail -n 1 | sed 's/^applying: //' || true)"
    echo "ERROR: 迁移 ${failed:-（未知）} 失败（已回滚，未登记台账），修复后重跑" >&2
    tail -n 30 "$LOG_FILE" >&2
    exit 1
fi

cat "$LOG_FILE"
pending_count="$(grep -c '^applying: ' "$LOG_FILE" || true)"
skipped_count="$(grep -c '^skipped: ' "$LOG_FILE" || true)"
echo "migrate done: applied=${pending_count:-0}, skipped(already applied)=${skipped_count:-0}"
