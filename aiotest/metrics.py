# encoding: utf-8
"""
AioTest性能指标模块

提供基于Prometheus的性能指标收集和报告功能，支持HTTP请求监控、
节点资源监控和自定义业务指标。

特性：

- 事件驱动的指标收集
- 统一的指标管理（请求数据 + 节点指标数据 + 用户活动数据）
- 解耦的架构设计
- 分布式节点支持

使用示例：
    # 初始化指标收集器
    collector = init_unified_collector("local", node_id="worker1")

    # 启动指标收集器（在异步上下文中）
    await collector.start()

    # 触发请求指标事件
    await request_metrics.fire(metrics=request_data)

    # 记录节点指标（Local/Master节点由Runner定期调用，Worker节点通过心跳系统传递）
    metrics_data = {
        "cpu_percent": 45.2,
        "active_users": 10,
        "worker_id": "worker1"
    }
    await collector.record_node_metrics(metrics_data)

    # 停止指标收集器
    await collector.stop()
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

from aiotest.events import request_metrics
from aiotest.logger import logger

# 自定义指标注册表，用于隔离指标
REGISTRY = CollectorRegistry()


@dataclass
class RequestMetrics:
    """请求指标数据结构"""
    request_id: str
    method: str
    endpoint: str
    status_code: int = 0
    duration: float = 0.0  # 单位秒
    response_size: int = 0  # 响应体大小（字节）
    error: Optional[Dict[str, Any]] = None
    extra: Optional[Dict[str, Any]] = None
    timestamp: float = field(default_factory=time.time)
    assertion_result: str = "unknown"  # "pass" 或 "fail"


# Prometheus 指标定义
REQUEST_COUNTER = Counter(
    'aiotest_http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code', 'assertion_result'],
    registry=REGISTRY
)

REQUEST_DURATION = Histogram(
    'aiotest_http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=[0.1, 0.25, 0.5, 0.8, 1.0, 2.5, 5.0, 10.0, 30.0],
    registry=REGISTRY
)

RESPONSE_SIZE = Histogram(
    'aiotest_http_response_size_bytes',
    'HTTP response size in bytes',
    ['method', 'endpoint'],
    buckets=(100, 1000, 10000, 100000, 1e6),
    registry=REGISTRY
)

WORKER_CPU_USAGE = Gauge(
    'aiotest_worker_cpu_percent',
    'Worker CPU usage percentage',
    ['worker_id', 'machine_id'],
    registry=REGISTRY
)

WORKER_ACTIVE_USERS = Gauge(
    'aiotest_worker_active_users',
    'Number of active users on worker',
    ['worker_id'],
    registry=REGISTRY
)

# 记录断言失败的信息 ：当请求中的断言失败时，会触发 ERROR_COUNTER 记录
# 记录其他类型的错误 ：包括网络错误、超时错误、HTTP 错误 ：4xx、5xx 状态码（当这些被断言为失败时）等
# 提供详细的错误分类 ：通过多个标签提供错误的详细信息
# 查看接口的响应数据 ：错误消息中包含接口的响应数据，便于调试
ERROR_COUNTER = Counter(
    'aiotest_errors_total',
    'Total errors with detailed information',
    ['error_type', 'method', 'endpoint', 'status_code', 'error_message'],
    registry=REGISTRY
)


class MetricsCollector:
    """统一的指标收集器"""

    def __init__(self, node_type: str = "local", redis_client=None, node_id: str = "local",
                 coordinator=None, batch_size: int = 100, flush_interval: float = 1.0,
                 buffer_size: int = 10000):
        """
        初始化指标收集器

        参数：
            node_type: 节点类型 (local/master/worker)
            redis_client: Redis客户端
            node_id: 节点ID
            coordinator: 分布式协调器
            batch_size: 批量上传的大小
            flush_interval: 刷新间隔（秒）
            buffer_size: 本地缓冲区大小
        """
        self.node_type = node_type
        self.node_id = node_id
        self.redis_client = redis_client
        self.coordinator = coordinator

        # 批量上传配置
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.buffer_size = buffer_size

        # 本地缓冲区
        self._metrics_buffer: List[Dict[str, Any]] = []
        self._buffer_lock = asyncio.Lock()
        self._flush_task = None

    async def start(self):
        """启动指标收集器"""
        await self._register_event_handlers()

        # 启动定期刷新任务
        if self.node_type == "worker":
            self._flush_task = asyncio.create_task(self._flush_buffer())

        logger.info("指标收集器已启动，节点ID: %s", self.node_id)

    async def stop(self):
        """停止指标收集器"""
        # 停止定期刷新任务
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        # 最后一次刷新缓冲区
        if self.node_type == "worker" and self._metrics_buffer:
            await self._do_flush()

        logger.info("指标收集器已停止，节点ID: %s", self.node_id)

    async def _flush_buffer(self):
        """定期刷新缓冲区"""
        while True:
            try:
                await asyncio.sleep(self.flush_interval)
                await self._do_flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("刷新指标缓冲区失败: %s", e)

    async def _do_flush(self):
        """执行缓冲区刷新"""
        async with self._buffer_lock:
            if not self._metrics_buffer:
                return

            # 批量处理缓冲区数据
            # 如果缓冲区数据量 >= batch_size，取 batch_size 条数据
            # 如果缓冲区数据量 < batch_size，取所有数据（避免延迟）
            batch_size = min(len(self._metrics_buffer), self.batch_size)
            batch = self._metrics_buffer[:batch_size]
            self._metrics_buffer = self._metrics_buffer[batch_size:]

        if batch:
            try:
                await self._forward_batch_to_redis(batch)
            except Exception as e:
                logger.warning("转发指标批次失败: %s", e)
                # 失败时将数据放回缓冲区
                async with self._buffer_lock:
                    self._metrics_buffer = batch + self._metrics_buffer

    async def record_node_metrics(self, metrics_data: dict) -> None:
        """
        记录节点指标数据（统一接口，支持分布式和本地模式）

        参数：
            metrics_data: 节点指标数据字典，包含cpu_percent, active_users, status等
                      - 对于Local/Master节点：定期上报的CPU和用户数
                      - 对于Worker节点：心跳系统传递的数据

        说明：
            - Local/Master节点：直接记录自身指标到Prometheus
            - Master节点：还会记录来自Worker节点的心跳数据
            - Worker节点：不直接调用此方法，而是通过心跳系统将数据传递给Master
        """
        try:
            cpu_percent = float(metrics_data.get('cpu_percent', 0.0))
            active_users = int(metrics_data.get('active_users', 0))
            worker_id = metrics_data.get('worker_id', self.node_id)
            machine_id = metrics_data.get('machine_id', 'unknown')

            # 记录到Prometheus
            self._record_cpu_usage(worker_id, machine_id, cpu_percent)
            self._record_active_users(worker_id, active_users)

        except (ValueError, TypeError) as e:
            logger.warning("记录节点指标失败: %s", e)

    def _record_cpu_usage(self, worker_id: str, machine_id: str, cpu_percent: float) -> None:
        """记录CPU使用率指标"""
        WORKER_CPU_USAGE.labels(
            worker_id=worker_id,
            machine_id=machine_id).set(cpu_percent)

    def _record_active_users(self, worker_id: str, active_users: int) -> None:
        """记录活跃用户数指标"""
        WORKER_ACTIVE_USERS.labels(worker_id=worker_id).set(active_users)

    async def _register_event_handlers(self):
        """注册指标事件处理器"""
        await request_metrics.add_handler(self.process_request_metrics)

    async def process_request_metrics(self, **kwargs) -> None:
        """
        处理请求数据（统一接口）

        根据节点类型选择不同的上报方式：
        - local: 直接上报到 Prometheus
        - worker: 转发到 Redis 供 Master 收集

        参数：
            metrics: RequestMetrics 对象
        """
        try:
            # 获取metrics数据
            metrics = kwargs.get('metrics')
            if not metrics:
                return

            # 数据上报（根据节点类型）
            if self.node_type in ("local", "master"):
                # Local 或 Master 节点：直接上报到 Prometheus
                self._report_to_prometheus_from_metrics(metrics)
            elif self.node_type == "worker":
                # Worker 节点：添加到本地缓冲区，等待批量发送到 Redis
                await self._add_metrics_to_buffer(metrics)

        except Exception as e:
            logger.warning("处理请求指标失败: %s", e)

    def _report_to_prometheus_from_metrics(
            self, metrics: RequestMetrics) -> None:
        """从 RequestMetrics 对象上报数据到 Prometheus"""
        method = metrics.method
        endpoint = metrics.endpoint
        status_code = str(metrics.status_code)
        duration = metrics.duration
        response_size = metrics.response_size
        assertion_result = metrics.assertion_result

        # 记录 Prometheus 指标
        self._record_request_counter(method, endpoint, status_code, assertion_result)
        self._record_request_duration(method, endpoint, duration)
        self._record_response_size(method, endpoint, response_size)

        # 记录错误指标
        if metrics.error:
            self._record_error_metrics(metrics, method, endpoint, status_code)

    def _record_request_counter(self, method: str, endpoint: str, status_code: str,
                               assertion_result: str) -> None:
        """记录请求计数指标"""
        REQUEST_COUNTER.labels(
            method=method,
            endpoint=endpoint,
            status_code=status_code,
            assertion_result=assertion_result
        ).inc()

    def _record_request_duration(self, method: str, endpoint: str, duration: float) -> None:
        """记录请求耗时指标"""
        REQUEST_DURATION.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)

    def _record_response_size(self, method: str, endpoint: str, response_size: int) -> None:
        """记录响应大小指标"""
        RESPONSE_SIZE.labels(
            method=method,
            endpoint=endpoint
        ).observe(response_size)

    def _record_error_metrics(self, metrics: RequestMetrics, method: str, endpoint: str,
                             status_code: str) -> None:
        """记录错误指标"""
        error_message = str(metrics.error.get('message', 'unknown'))

        # 限制错误消息长度，避免过长
        if len(error_message) > 200:
            error_message = error_message[:200]

        ERROR_COUNTER.labels(
            error_type=metrics.error.get('exc_type', 'unknown'),
            method=method,
            endpoint=endpoint,
            status_code=status_code,
            error_message=error_message
        ).inc()

    async def _add_metrics_to_buffer(self, metrics: RequestMetrics) -> None:
        """
        从 RequestMetrics 对象转换数据并添加到本地缓冲区，等待批量发送到 Redis

        参数：
            metrics: RequestMetrics 对象，包含请求相关的指标数据
        """
        if not self.coordinator:
            return

        # 转换为字典格式并添加 worker 信息
        metrics_dict = self._convert_metrics_to_dict(metrics)

        # 添加到缓冲区
        await self._append_to_buffer(metrics_dict)

    def _convert_metrics_to_dict(self, metrics: RequestMetrics) -> Dict[str, Any]:
        """将RequestMetrics对象转换为字典格式"""
        return {
            'request_id': metrics.request_id,
            'method': metrics.method,
            'endpoint': metrics.endpoint,
            'status_code': metrics.status_code,
            'duration': metrics.duration,
            'response_size': metrics.response_size,
            'error': metrics.error,
            'timestamp': metrics.timestamp,
            'assertion_result': metrics.assertion_result,
            'worker_id': self.node_id
        }

    async def _append_to_buffer(self, metrics_dict: Dict[str, Any]) -> None:
        """将指标数据添加到缓冲区"""
        async with self._buffer_lock:
            if len(self._metrics_buffer) < self.buffer_size:
                self._metrics_buffer.append(metrics_dict)
            else:
                # 缓冲区已满，丢弃最旧的数据
                self._metrics_buffer.pop(0)
                self._metrics_buffer.append(metrics_dict)
                logger.warning("指标缓冲区已满，丢弃最旧的指标")

    async def _forward_batch_to_redis(
            self, batch: List[Dict[str, Any]]) -> None:
        """批量转发数据到 Redis"""
        if not self.coordinator:
            return

        # 批量发布请求数据
        await self.coordinator.publish("request_metrics", batch, worker_id=self.node_id)

    def get_metrics_export(self) -> str:
        """获取 Prometheus 格式的指标导出，仅测试使用"""
        try:
            return generate_latest(REGISTRY).decode('utf-8')
        except Exception as e:
            logger.error("获取指标导出失败: %s", e)
            return ""


# 全局指标收集器实例
_UNIFIED_COLLECTOR: Optional[MetricsCollector] = None


def get_unified_collector() -> MetricsCollector:
    """获取统一的指标收集器实例"""
    global _UNIFIED_COLLECTOR
    if _UNIFIED_COLLECTOR is None:
        raise RuntimeError("统一的指标收集器未初始化。"
                           "请在运行器中初始化它。")
    return _UNIFIED_COLLECTOR


def init_unified_collector(node_type: str = "local", redis_client=None, node_id: str = "local",
                           coordinator=None, batch_size: int = 100, flush_interval: float = 1.0,
                           buffer_size: int = 10000) -> MetricsCollector:
    """初始化统一的指标收集器"""
    global _UNIFIED_COLLECTOR
    _UNIFIED_COLLECTOR = MetricsCollector(
        node_type,
        redis_client,
        node_id,
        coordinator,
        batch_size=batch_size,
        flush_interval=flush_interval,
        buffer_size=buffer_size
    )
    return _UNIFIED_COLLECTOR


def is_unified_collector_initialized() -> bool:
    """检查统一指标收集器是否已初始化"""
    global _UNIFIED_COLLECTOR
    return _UNIFIED_COLLECTOR is not None
