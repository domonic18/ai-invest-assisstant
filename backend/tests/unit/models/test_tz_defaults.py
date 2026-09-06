"""时区红线：模型 timestamptz 列默认值必须是 aware UTC。

背景：36 处 naive ``datetime.utcnow`` 默认值曾遍布模型层——insert 未显式传
时间戳列时，PostgreSQL 会把 naive 值按 UTC 解释尚可，但本地时区一旦非 UTC
（应用容器 TZ=Asia/Shanghai）即产生 8 小时漂移。本测试遍历全部 ORM 模型的
timestamptz 列，断言可调用默认值产出带 tzinfo 的 UTC 时间，防止回潮。
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import DateTime

from app.core.database import Base
from app.models import *  # noqa: F401,F403 —— 触发全部模型注册进 metadata
from app.models import __all__ as _model_all  # noqa: F401


def _model_classes() -> list[type]:
    import app.models as models_pkg

    return [
        getattr(models_pkg, name)
        for name in models_pkg.__all__
        if isinstance(getattr(models_pkg, name), type)
        and issubclass(getattr(models_pkg, name), Base)
    ]


@pytest.mark.unit
def test_all_timestamptz_defaults_are_aware_utc():
    models = _model_classes()
    assert len(models) >= 25, "模型注册数量异常，检查 app.models 导入"

    checked = 0
    for model in models:
        for column in model.__table__.columns:
            if not isinstance(column.type, DateTime) or not column.type.timezone:
                continue
            default = column.default
            if default is None or not default.is_callable:
                continue
            value = default.arg(None) if default.arg.__code__.co_argcount else default.arg()
            assert isinstance(value, datetime), (
                f"{model.__tablename__}.{column.name} 默认值应返回 datetime"
            )
            assert value.tzinfo is not None, (
                f"{model.__tablename__}.{column.name} 默认值是 naive datetime"
                "（时区红线：timestamptz 默认值必须用 app.core.clock.utc_now）"
            )
            assert value.utcoffset() == timezone.utc.utcoffset(None), (
                f"{model.__tablename__}.{column.name} 默认值必须是 UTC"
            )
            checked += 1

    assert checked >= 30, f"仅校验了 {checked} 列，timestamptz 默认值覆盖面异常"
