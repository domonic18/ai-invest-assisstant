"""通用服务：MinIO 对象存储、通用知识库 RAG 检索（消费方为 agent tools 与 reports）。"""

from app.services.common import knowledge_base_service, minio_service
from app.services.common.knowledge_base_service import (
    KnowledgeBaseService,
    get_knowledge_base_service,
)
from app.services.common.minio_service import MinIOService, get_minio_service

__all__ = [
    "KnowledgeBaseService",
    "MinIOService",
    "get_knowledge_base_service",
    "get_minio_service",
    "knowledge_base_service",
    "minio_service",
]
