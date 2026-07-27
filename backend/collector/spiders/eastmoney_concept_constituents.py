"""东方财富概念板块成分股采集器。

通过 akshare 获取东方财富概念列表与每个概念的成分股，写入
mapping_stock_concept 表，供个股详情页展示“包含的概念”。

说明：akshare 在 1.14.17 移除了同花顺概念成分股接口
stock_board_concept_cons_ths，因此本采集器改用东方财富的
stock_board_concept_cons_em 作为替代数据源。
"""

from typing import Any, ClassVar

import structlog

from collector.core.base import PostgresCollector
from collector.core.parsing import clean_stock_code, to_optional_str

logger = structlog.get_logger(__name__)


class EastmoneyConceptConstituentCollector(PostgresCollector):
    """东方财富概念成分股采集器，写入 mapping_stock_concept。"""

    table = "mapping_stock_concept"
    conflict_key = "stock_code, concept_code"
    update_columns: ClassVar[list[str]] = [
        "concept_name",
        "source",
        "updated_at",
    ]
    normalize = False
    key_fields: ClassVar[list[str]] = ["stock_code", "concept_code"]
    required_fields: ClassVar[list[str]] = [
        "stock_code",
        "concept_code",
        "concept_name",
    ]

    async def collect(self, **kwargs: Any) -> list[dict[str, Any]]:
        import akshare as ak  # type: ignore[import-untyped]

        try:
            concept_df = ak.stock_board_concept_name_em()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"获取东方财富概念列表失败: {exc}") from exc

        if concept_df is None or concept_df.empty:
            return []

        concept_rows = concept_df.to_dict(orient="records")
        all_items: list[dict[str, Any]] = []

        for concept_row in concept_rows:
            concept_code = to_optional_str(concept_row.get("板块代码"))
            concept_name = to_optional_str(concept_row.get("板块名称"))
            if not concept_code or not concept_name:
                continue

            try:
                cons_df = ak.stock_board_concept_cons_em(symbol=concept_name)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "concept_constituents_fetch_failed",
                    concept_code=concept_code,
                    concept_name=concept_name,
                    error=str(exc),
                )
                continue

            if cons_df is None or cons_df.empty:
                continue

            for stock_row in cons_df.to_dict(orient="records"):
                raw_code = stock_row.get("代码")
                if raw_code is None:
                    continue
                stock_code = clean_stock_code(raw_code)
                if not stock_code or not stock_code.isdigit():
                    continue
                all_items.append(
                    {
                        "stock_code": stock_code,
                        "concept_code": concept_code,
                        "concept_name": concept_name,
                        "source": "eastmoney",
                    }
                )

        return all_items
