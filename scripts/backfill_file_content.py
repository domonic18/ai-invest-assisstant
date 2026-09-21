"""一次性回填：MinIO 重抽研报/财报 PDF 全文 → file_metadata.content（去 ES 配套）。

用法（web 容器内，读容器 env 的 MINIO_* / DATABASE_URL）：

    docker cp scripts/backfill_file_content.py <web容器>:/tmp/backfill.py
    docker exec <web容器> python /tmp/backfill.py [--dry-run] [--limit N]

- 只处理 content IS NULL 的 research_report/financial_report 行，可安全中断重跑；
- MinIO 缺文件 / pypdf 抽取失败逐条 best-effort 跳过并计数，不阻塞整体；
- 不依赖 ES（与 ES 退役顺序解耦）。
"""

import argparse
import asyncio
import os
import sys

import asyncpg

FILE_TYPES = ("research_report", "financial_report")


def pg_dsn() -> str:
    url = os.environ.get("DATABASE_URL", "")
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="最多处理行数（0=全部）")
    args = parser.parse_args()

    dsn = pg_dsn()
    if not dsn:
        print("DATABASE_URL 未配置", file=sys.stderr)
        return 2

    from app.services.common.minio_service import get_minio_service
    from app.services.common.pdf_text import extract_pdf_text

    conn = await asyncpg.connect(dsn)
    minio = get_minio_service()
    rows = await conn.fetch(
        "SELECT id, file_path FROM file_metadata "
        "WHERE content IS NULL AND file_type = ANY($1) ORDER BY id",
        list(FILE_TYPES),
    )
    if args.limit > 0:
        rows = rows[: args.limit]

    updated = skipped_minio = skipped_extract = 0
    for row_id, file_path in rows:
        try:
            data = await minio.download_file(file_path)
        except Exception as exc:  # noqa: BLE001
            print(f"[minio-miss] id={row_id} path={file_path}: {exc}", flush=True)
            skipped_minio += 1
            continue
        content = await extract_pdf_text(data)
        if not content:
            print(f"[extract-miss] id={row_id} path={file_path}", flush=True)
            skipped_extract += 1
            continue
        if args.dry_run:
            updated += 1
            continue
        await conn.execute(
            "UPDATE file_metadata SET content = $1 WHERE id = $2", content, row_id
        )
        updated += 1
    await conn.close()

    print(f"dry_run={args.dry_run} total={len(rows)}")
    print(f"updated={updated} skipped_minio={skipped_minio} skipped_extract={skipped_extract}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
