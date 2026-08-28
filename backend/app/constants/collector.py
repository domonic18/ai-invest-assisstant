"""Celery 采集器常量。"""

from enum import Enum


class CollectorStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


class CollectorQueue(str, Enum):
    REALTIME = "collector.realtime"
    BATCH = "collector.batch"
    HEAVY = "collector.heavy"


class CollectorMode(str, Enum):
    BEAT = "beat"
    WORKER = "worker"
