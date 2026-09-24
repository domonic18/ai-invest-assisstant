"""一次性回填：ES kb-knowledge-v3 投影 embedding → PG 检索列（方案 B 零重嵌入）。

用法（web 容器内，读容器 env 的 ELASTICSEARCH_URL / DATABASE_URL）：

    docker cp scripts/backfill_kb_embedding_from_es.py <web容器>:/tmp/backfill.py
    docker exec <web容器> python /tmp/backfill.py [--index kb-knowledge-v3] [--dry-run]

- doc id 形如 point-12/seg-3/img-5，embedding 为 2048 维（halfvec 列同维）；
- 写入 ``embedding`` 并清 ``embedding_dirty``；行已不存在（0 rowcount）单独计数；
- 检索可见性由行状态 + 检索过滤保证，投影后转为不可见的行残留向量无害；
- v3 之后新增的行不在 ES 内，脏标保留由 kb-index 增量物化。
"""

import argparse
import asyncio
import json
import os
import sys

import asyncpg
import httpx

EXPECTED_DIMS = 2048
TABLE_BY_PREFIX = {"point": "kb_knowledge_point", "seg": "kb_transcript_segment",
                   "img": "kb_image_asset"}
SCROLL_SIZE = 500


async def scroll_embeddings(es_url: str, index: str):
    async with httpx.AsyncClient(base_url=es_url, timeout=30) as client:
        resp = await client.post(
            f"/{index}/_search",
            json={
                "size": SCROLL_SIZE,
                "_source": ["embedding"],
                "query": {"exists": {"field": "embedding"}},
                "sort": ["_doc"],
            },
            params={"scroll": "2m"},
        )
        resp.raise_for_status()
        payload = resp.json()
        scroll_id = payload["_scroll_id"]
        hits = payload["hits"]["hits"]
        while hits:
            for hit in hits:
                yield hit["_id"], hit["_source"].get("embedding")
            resp = await client.post(
                "/_search/scroll",
                json={"scroll": "2m", "scroll_id": scroll_id},
            )
            resp.raise_for_status()
            payload = resp.json()
            scroll_id = payload["_scroll_id"]
            hits = payload["hits"]["hits"]
        await client.request(
            "DELETE", "/_search/scroll", json={"scroll_id": [scroll_id]}
        )


def pg_dsn() -> str:
    url = os.environ.get("DATABASE_URL", "")
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", default="kb-knowledge-v3")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    es_url = os.environ.get("ELASTICSEARCH_URL", "http://elasticsearch:9200").rstrip("/")
    dsn = pg_dsn()
    if not dsn:
        print("DATABASE_URL 未配置", file=sys.stderr)
        return 2

    updated = {k: 0 for k in TABLE_BY_PREFIX}
    missing = {k: 0 for k in TABLE_BY_PREFIX}
    bad_dims = 0
    conn = await asyncpg.connect(dsn)
    try:
        async for doc_id, vector in scroll_embeddings(es_url, args.index):
            prefix, _, raw = doc_id.partition("-")
            table = TABLE_BY_PREFIX.get(prefix)
            if table is None or not raw.isdigit() or not vector:
                continue
            if len(vector) != EXPECTED_DIMS:
                bad_dims += 1
                continue
            literal = json.dumps(vector, separators=(",", ":"))
            if args.dry_run:
                updated[prefix] += 1
                continue
            result = await conn.execute(
                f"UPDATE {table} SET embedding = $1::halfvec, "
                "embedding_dirty = false WHERE id = $2",
                literal,
                int(raw),
            )
            if result.endswith(" 1"):
                updated[prefix] += 1
            else:
                missing[prefix] += 1
    finally:
        await conn.close()

    print(f"index={args.index} dry_run={args.dry_run}")
    print(f"updated={updated} missing={missing} bad_dims={bad_dims}")
    return 0 if bad_dims == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
