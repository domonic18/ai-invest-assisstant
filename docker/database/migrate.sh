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
# ============================================================
set -euo pipefail
export LC_ALL=C

: "${PGDATABASE:?PGDATABASE is required (e.g. invest)}"
: "${PGUSER:?PGUSER is required}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIGRATIONS_DIR="${MIGRATIONS_DIR:-$SCRIPT_DIR/migrations}"

# --- psql 调用方式二选一：宿主机直连 / postgres 容器 exec ---
if command -v psql >/dev/null 2>&1; then
    PGHOST="${PGHOST:-localhost}"
    psql_query() { psql -v ON_ERROR_STOP=1 -qAt -X -h "$PGHOST" -U "$PGUSER" -d "$PGDATABASE" "$@"; }
    # 迁移 SQL 与台账登记同事务（-c/-f 按出现顺序执行：先文件后登记）
    psql_apply() { psql -v ON_ERROR_STOP=1 -q -X -h "$PGHOST" -U "$PGUSER" -d "$PGDATABASE" \
        --single-transaction -f "$1" -c "$2"; }
else
    command -v docker >/dev/null 2>&1 \
        || { echo "ERROR: 宿主机既无 psql 也无 docker，无法执行迁移" >&2; exit 1; }
    docker compose exec -T postgres pg_isready -U "$PGUSER" -d "$PGDATABASE" >/dev/null 2>&1 \
        || { echo "ERROR: postgres 容器未运行或未就绪，先执行 docker compose up -d postgres 并等健康" >&2; exit 1; }
    psql_query() { docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -qAt -X \
        -U "$PGUSER" -d "$PGDATABASE" "$@"; }
    psql_apply() { { cat "$1"; printf '%s\n' "$2"; } | docker compose exec -T postgres psql \
        -v ON_ERROR_STOP=1 -q -X -U "$PGUSER" -d "$PGDATABASE" --single-transaction -f -; }
fi

psql_query -c "CREATE TABLE IF NOT EXISTS schema_migrations (
    name        TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
)"

applied="$(psql_query -c "SELECT name FROM schema_migrations")"
pending_count=0
skipped_count=0

for f in "$MIGRATIONS_DIR"/*.sql; do
    name="$(basename "$f")"
    if grep -qxF "$name" <<<"$applied"; then
        skipped_count=$((skipped_count + 1))
        continue
    fi
    # 文件名白名单：防注入，也防误放杂文件
    if ! grep -qxE '[A-Za-z0-9._-]+' <<<"$name"; then
        echo "ERROR: 非法迁移文件名，跳过：$name" >&2
        exit 1
    fi
    echo "applying: $name"
    # --single-transaction：迁移 SQL 与台账登记同事务，失败一起回滚
    if ! psql_apply "$f" "INSERT INTO schema_migrations(name) VALUES ('$name')"; then
        echo "ERROR: 迁移 $name 失败（已回滚，未登记台账），修复后重跑" >&2
        exit 1
    fi
    applied+="$name"$'\n'
    pending_count=$((pending_count + 1))
done

echo "migrate done: applied=$pending_count, skipped(already applied)=$skipped_count"
