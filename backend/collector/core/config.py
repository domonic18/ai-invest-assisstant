"""Collector 配置入口。

唯一真相源是 app.core.config.Settings（Pydantic Settings + .env），
本模块只做类型适配：SQLAlchemy/redis 客户端需要 str 而非 Pydantic Url。
"""

from app.core.config import get_settings

_settings = get_settings()

database_url: str = str(_settings.database_url)
redis_url: str = str(_settings.redis_url)

celery_broker_url: str = _settings.celery_broker_url
celery_result_backend: str = _settings.celery_result_backend
celery_task_default_queue: str = _settings.celery_task_default_queue
celery_result_expires: int = _settings.celery_result_expires
