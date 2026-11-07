#!/usr/bin/env python3
"""迁移幂等性静态检查（CI 门禁）。

CLAUDE.md「数据库迁移规范」要求新迁移必须幂等（IF NOT EXISTS / ON CONFLICT DO NOTHING）。
幂等性最终要由数据库验证，但台账制下重放只会跳过已登记的迁移，
「applied=0」的重放断言是恒真的，验证不到 SQL 本身——本脚本补的就是这个缺口：
逐条语句静态扫描，拦下会二次执行就报错的写法。

历史迁移 forward-only 不可修改，用 ALLOWLIST 豁免并在注释里写明原因。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "docker" / "database" / "migrations"

# 历史迁移豁免：forward-only 禁止修改，只能记录在案
ALLOWLIST = {
    # 建表/加列/插入均无幂等保护；forward-only 不可回改
    "20261018a_create_user_group.sql",
}

RULES = (
    ("CREATE_TABLE", re.compile(r"^\s*create\s+table\b", re.I), re.compile(r"\bif\s+not\s+exists\b", re.I)),
    ("ALTER_ADD_COLUMN", re.compile(r"^\s*alter\s+table\b.*\badd\s+column\b", re.I | re.S), re.compile(r"\bif\s+not\s+exists\b", re.I)),
    ("CREATE_INDEX", re.compile(r"^\s*create\s+(unique\s+)?index\b", re.I), re.compile(r"\bif\s+not\s+exists\b", re.I)),
    ("CREATE_VIEW", re.compile(r"^\s*create\s+(or\s+replace\s+)?view\b", re.I), re.compile(r"\bif\s+not\s+exists\b", re.I)),
    ("CREATE_SEQUENCE", re.compile(r"^\s*create\s+sequence\b", re.I), re.compile(r"\bif\s+not\s+exists\b", re.I)),
    ("INSERT", re.compile(r"^\s*insert\s+into\b", re.I), re.compile(r"\bon\s+conflict\b", re.I)),
)


def strip_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    return re.sub(r"--[^\n]*", " ", sql)


def split_statements(sql: str) -> list[str]:
    return [s.strip() for s in sql.split(";") if s.strip()]


def main() -> int:
    if not MIGRATIONS_DIR.is_dir():
        print(f"ERROR: 迁移目录不存在：{MIGRATIONS_DIR}", file=sys.stderr)
        return 1

    violations: list[str] = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if path.name in ALLOWLIST:
            continue
        sql = strip_comments(path.read_text(encoding="utf-8"))
        for stmt in split_statements(sql):
            head = stmt.lstrip().lstrip("(").lstrip()
            for name, trigger, guard in RULES:
                if trigger.search(head) and not guard.search(stmt):
                    snippet = " ".join(stmt.split())[:120]
                    violations.append(f"{path.name}: {name} 缺少幂等保护 → {snippet}")

    if violations:
        print("ERROR: 迁移未满足幂等要求（CLAUDE.md「数据库迁移规范」）：", file=sys.stderr)
        for v in violations:
            print(f"  {v}", file=sys.stderr)
        print(
            "\n修法：CREATE TABLE/ADD COLUMN/CREATE INDEX/VIEW/SEQUENCE 加 IF NOT EXISTS；"
            "INSERT 加 ON CONFLICT DO NOTHING。",
            file=sys.stderr,
        )
        return 1

    print("迁移幂等性检查通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
