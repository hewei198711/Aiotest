
"""
AioTest - 异步负载测试框架

一个基于 asyncio 的高性能负载测试框架，支持分布式测试、
实时监控和灵活的用户行为模拟。

主要特性:
- 异步高性能，支持大规模并发测试
- 分布式架构，支持多节点协调
- 灵活的用户行为定义和权重分配
- 实时性能监控和指标收集
- 完善的错误处理和日志系统
"""

from .clients import HTTPClient, configure_connector
from .distributed_coordinator import DistributedLock, RedisConnection
from .events import (
    EventHook,
    Events,
    events,
    init_events,
    request_metrics,
    startup_completed,
    test_quit,
    test_start,
    test_stop,
    worker_request_metrics,
)
from .exception import InvalidRateError, InvalidUserCountError, RunnerError
from .logger import logger
from .main import main
from .shape import LoadUserShape
from .users import ExecutionMode, HttpUser, User, WaitTimeResolver, WaitTimeType, weight

__version__ = "1.0.5"
__author__ = "AioTest Team"
__description__ = "Asyncio-based load testing framework"

__all__ = [
    # Core classes
    "User",
    "HttpUser",
    "HTTPClient",
    "LoadUserShape",

    # Utilities
    "WaitTimeType",
    "WaitTimeResolver",
    "weight",
    "ExecutionMode",
    "configure_connector",

    # Event system
    "events",
    "EventHook",
    "Events",
    "init_events",
    "test_start",
    "test_stop",
    "test_quit",
    "startup_completed",
    "request_metrics",
    "worker_request_metrics",

    # Systems
    "logger",
    "RedisConnection",
    "DistributedLock",

    # Exceptions
    "RunnerError",
    "InvalidUserCountError",
    "InvalidRateError",

    # Main entry point
    "main",
]
