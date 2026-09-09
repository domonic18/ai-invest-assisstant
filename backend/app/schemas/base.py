"""schema 共享基类。

camelCase wire 约定见 ``chain.py`` 先例：Python 侧字段保留 snake_case
（与 ORM 模型一致），wire format 输出 camelCase，与 ``shared/types``
单一真相源对齐。新域 schema 迁移时继承 ``CamelModel``。
"""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """响应 schema 基类：camelCase 序列化 + 允许按字段名构造/校验。"""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )
