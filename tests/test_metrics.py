# encoding: utf-8

import asyncio
import time

import allure
import pytest

from aiotest.metrics import (MetricsCollector, RequestMetrics,
                             get_unified_collector, init_unified_collector,
                             is_unified_collector_initialized)


@allure.feature("RequestMetrics")
class TestRequestMetrics:
    """RequestMetrics 数据类的测试用例"""

    @allure.story("初始化")
    @allure.title("测试 RequestMetrics 基本初始化")
    @allure.severity(allure.severity_level.NORMAL)
    def test_initialization(self):
        """测试 RequestMetrics 初始化时正确设置默认值"""
        before_init = time.time()
        metrics = RequestMetrics(
            request_id="test-001",
            method="GET",
            endpoint="/api/users"
        )
        after_init = time.time()

        assert metrics.request_id == "test-001"
        assert metrics.method == "GET"
        assert metrics.endpoint == "/api/users"
        assert metrics.status_code == 0
        assert metrics.duration == 0.0
        assert metrics.response_size == 0
        assert metrics.error is None
        assert metrics.extra is None
        assert before_init <= metrics.timestamp <= after_init

    @allure.story("初始化")
    @allure.title("测试 RequestMetrics 完整参数初始化")
    @allure.severity(allure.severity_level.NORMAL)
    def test_full_initialization(self):
        """测试带所有参数的 RequestMetrics 初始化"""
        timestamp = time.time()
        error_info = {
            "type": "ConnectionError",
            "message": "Connection refused"}
        extra_info = {"user_id": 123, "request_size": 1024}

        metrics = RequestMetrics(
            request_id="test-002",
            method="POST",
            endpoint="/api/users",
            status_code=201,
            duration=0.5,
            response_size=2048,
            error=error_info,
            extra=extra_info,
            timestamp=timestamp
        )

        assert metrics.request_id == "test-002"
        assert metrics.method == "POST"
        assert metrics.endpoint == "/api/users"
        assert metrics.status_code == 201
        assert metrics.duration == 0.5
        assert metrics.response_size == 2048
        assert metrics.error == error_info
        assert metrics.extra == extra_info
        assert metrics.timestamp == timestamp


@allure.feature("MetricsCollector")
class TestMetricsCollector:
    """MetricsCollector 类的测试用例"""

    @allure.story("初始化")
    @allure.title("测试 MetricsCollector 基本初始化")
    @allure.severity(allure.severity_level.NORMAL)
    def test_initialization(self):
        """测试 MetricsCollector 初始化时正确设置属性"""
        collector = MetricsCollector(
            node_type="local",
            node_id="test-worker-1",
            batch_size=50,
            flush_interval=2.0,
            buffer_size=5000
        )

        assert collector.node_type == "local"
        assert collector.node_id == "test-worker-1"
        assert collector.batch_size == 50
        assert collector.flush_interval == 2.0
        assert collector.buffer_size == 5000
        assert collector._metrics_buffer == []
        assert collector._buffer_lock is not None
        assert collector._flush_task is None

    @allure.story("初始化")
    @allure.title("测试 MetricsCollector 默认参数初始化")
    @allure.severity(allure.severity_level.NORMAL)
    def test_default_initialization(self):
        """测试使用默认参数的 MetricsCollector 初始化"""
        collector = MetricsCollector()

        assert collector.node_type == "local"
        assert collector.node_id == "local"
        assert collector.batch_size == 100
        assert collector.flush_interval == 1.0
        assert collector.buffer_size == 10000

    @allure.story("生命周期")
    @allure.title("测试 MetricsCollector 启动和停止")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_start_stop(self):
        """测试 MetricsCollector 的启动和停止"""
        collector = MetricsCollector(node_type="local", node_id="test-node")

        await collector.start()
        assert collector._flush_task is None

        await collector.stop()

    @allure.story("生命周期")
    @allure.title("测试 Worker 节点启动和停止")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_worker_start_stop(self):
        """测试 Worker 节点的 MetricsCollector 启动和停止"""
        collector = MetricsCollector(
            node_type="worker",
            node_id="test-worker-1",
            flush_interval=0.1
        )

        await collector.start()
        assert collector._flush_task is not None

        await collector.stop()
        await asyncio.sleep(0.05)
        assert collector._flush_task is None or collector._flush_task.done()

    @allure.story("节点指标")
    @allure.title("测试记录节点指标")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_record_node_metrics(self):
        """测试记录节点指标数据"""
        collector = MetricsCollector(node_type="local", node_id="test-node")

        metrics_data = {
            "cpu_percent": 45.5,
            "active_users": 10,
            "worker_id": "test-node"
        }

        await collector.record_node_metrics(metrics_data)

    @allure.story("节点指标")
    @allure.title("测试记录节点指标边界值")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.parametrize("cpu_percent,active_users", [
        (0.0, 0),
        (100.0, 1000),
        (50.5, 500),
    ])
    async def test_record_node_metrics_edge_cases(
            self, cpu_percent, active_users):
        """测试记录节点指标数据的边界情况"""
        collector = MetricsCollector(node_type="local", node_id="test-node")

        metrics_data = {
            "cpu_percent": cpu_percent,
            "active_users": active_users,
            "worker_id": "test-node"
        }

        await collector.record_node_metrics(metrics_data)

    @allure.story("节点指标")
    @allure.title("测试记录节点指标无效数据")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_record_node_metrics_invalid_data(self):
        """测试记录无效的节点指标数据"""
        collector = MetricsCollector(node_type="local", node_id="test-node")

        invalid_data = {
            "cpu_percent": "invalid",
            "active_users": "invalid"
        }

        await collector.record_node_metrics(invalid_data)


@allure.feature("请求指标处理")
class TestRequestMetricsProcessing:
    """请求指标处理的测试用例"""

    @allure.story("处理请求")
    @allure.title("测试 Local 节点处理请求指标")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_process_request_metrics_local(self):
        """测试 Local 节点处理请求指标"""
        collector = MetricsCollector(node_type="local", node_id="test-local")
        await collector.start()

        metrics = RequestMetrics(
            request_id="req-001",
            method="GET",
            endpoint="/api/users",
            status_code=200,
            duration=0.1,
            response_size=1024
        )

        await collector.process_request_metrics(metrics=metrics)

        await collector.stop()

    @allure.story("处理请求")
    @allure.title("测试 Master 节点处理请求指标")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_process_request_metrics_master(self):
        """测试 Master 节点处理请求指标"""
        collector = MetricsCollector(node_type="master", node_id="test-master")
        await collector.start()

        metrics = RequestMetrics(
            request_id="req-002",
            method="POST",
            endpoint="/api/login",
            status_code=201,
            duration=0.2,
            response_size=512
        )

        await collector.process_request_metrics(metrics=metrics)

        await collector.stop()

    @allure.story("处理请求")
    @allure.title("测试请求指标包含错误信息")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_process_request_metrics_with_error(self):
        """测试处理包含错误信息的请求指标"""
        collector = MetricsCollector(node_type="local", node_id="test-local")
        await collector.start()

        metrics = RequestMetrics(
            request_id="req-003",
            method="GET",
            endpoint="/api/error",
            status_code=500,
            duration=0.05,
            response_size=0,
            error={
                "exc_type": "ServerError",
                "message": "Internal server error"}
        )

        await collector.process_request_metrics(metrics=metrics)

        await collector.stop()

    @allure.story("处理请求")
    @allure.title("测试请求指标包含额外数据")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_process_request_metrics_with_extra(self):
        """测试处理包含额外数据的请求指标"""
        collector = MetricsCollector(node_type="local", node_id="test-local")
        await collector.start()

        metrics = RequestMetrics(
            request_id="req-004",
            method="GET",
            endpoint="/api/data",
            status_code=200,
            duration=0.3,
            response_size=4096,
            extra={"user_id": 123, "session_id": "abc123"}
        )

        await collector.process_request_metrics(metrics=metrics)

        await collector.stop()

    @allure.story("处理请求")
    @allure.title("测试处理空请求指标")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_process_empty_metrics(self):
        """测试处理空的请求指标"""
        collector = MetricsCollector(node_type="local", node_id="test-local")
        await collector.start()

        await collector.process_request_metrics()

        await collector.stop()


@allure.feature("Prometheus 指标")
class TestPrometheusMetrics:
    """Prometheus 指标相关的测试用例"""

    @allure.story("指标导出")
    @allure.title("测试获取 Prometheus 指标导出")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_get_metrics_export(self):
        """测试获取 Prometheus 格式的指标导出"""
        collector = MetricsCollector(node_type="local", node_id="test-export")
        await collector.start()

        metrics = RequestMetrics(
            request_id="req-005",
            method="GET",
            endpoint="/api/test",
            status_code=200,
            duration=0.1,
            response_size=1024
        )
        await collector.process_request_metrics(metrics=metrics)

        export = collector.get_metrics_export()
        assert isinstance(export, str)
        assert len(export) > 0

        await collector.stop()

    @allure.story("指标导出")
    @allure.title("测试空 MetricsCollector 导出")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_get_metrics_export_empty(self):
        """测试空 MetricsCollector 的指标导出"""
        collector = MetricsCollector(node_type="local", node_id="test-empty")
        await collector.start()

        export = collector.get_metrics_export()
        assert isinstance(export, str)

        await collector.stop()


@allure.feature("全局函数")
class TestGlobalFunctions:
    """全局初始化和管理函数的测试用例"""

    @allure.story("初始化")
    @allure.title("测试初始化统一指标收集器")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_init_unified_collector(self):
        """测试 init_unified_collector 函数"""
        collector = init_unified_collector(
            node_type="local",
            node_id="unified-test",
            batch_size=50,
            flush_interval=0.5
        )

        assert collector is not None
        assert collector.node_type == "local"
        assert collector.node_id == "unified-test"
        assert collector.batch_size == 50

        await collector.stop()

    @allure.story("初始化")
    @allure.title("测试获取统一指标收集器")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_get_unified_collector(self):
        """测试 get_unified_collector 函数"""
        collector = init_unified_collector(
            node_type="local",
            node_id="get-test"
        )

        result = get_unified_collector()
        assert result is collector

        await collector.stop()

    @allure.story("初始化")
    @allure.title("测试未初始化时获取收集器抛出异常")
    @allure.severity(allure.severity_level.NORMAL)
    def test_get_unified_collector_not_initialized(self):
        """测试未初始化时 get_unified_collector 抛出异常"""
        from aiotest import metrics as metrics_module
        metrics_module._UNIFIED_COLLECTOR = None

        with pytest.raises(RuntimeError):
            get_unified_collector()

    @allure.story("状态检查")
    @allure.title("测试检查统一收集器初始化状态")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_is_initialized(self):
        """测试 is_unified_collector_initialized 函数"""
        from aiotest import metrics as metrics_module
        metrics_module._UNIFIED_COLLECTOR = None

        assert is_unified_collector_initialized() is False


@allure.feature("缓冲区处理")
class TestBufferProcessing:
    """缓冲区处理相关的测试用例"""

    @allure.story("批量上传")
    @allure.title("测试数据量不足时的批量上传")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_batch_upload_with_insufficient_data(self):
        """测试当缓冲区数据量不足 batch_size 时，也能在刷新时上传所有可用数据"""
        # 创建一个 mock 的 coordinator 对象
        class MockCoordinator:
            async def publish(self, channel, data, worker_id=None):
                pass

        # 创建 Worker 类型的收集器，设置较小的 batch_size
        collector = MetricsCollector(
            node_type="worker",
            node_id="test-worker",
            batch_size=5,  # 设置 batch_size 为 5
            coordinator=MockCoordinator()  # 添加 mock coordinator
        )
        await collector.start()

        # 向缓冲区添加 3 条数据（少于 batch_size）
        for i in range(3):
            metrics = RequestMetrics(
                request_id=f"req-{i}",
                method="GET",
                endpoint="/api/test",
                status_code=200
            )
            await collector.process_request_metrics(metrics=metrics)

        # 检查缓冲区有 3 条数据
        assert len(collector._metrics_buffer) == 3

        # 手动调用刷新方法
        await collector._do_flush()

        # 检查缓冲区被清空（数据已上传）
        assert len(collector._metrics_buffer) == 0

        await collector.stop()

    @allure.story("状态检查")
    @allure.title("测试统一收集器指标导出")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_unified_collector_metrics_export(self):
        """测试统一收集器的指标导出"""
        collector = init_unified_collector(
            node_type="local", node_id="export-global")
        await collector.start()

        metrics = RequestMetrics(
            request_id="req-006",
            method="GET",
            endpoint="/api/global",
            status_code=200,
            duration=0.1,
            response_size=512
        )
        await collector.process_request_metrics(metrics=metrics)

        export = collector.get_metrics_export()
        assert isinstance(export, str)
        assert "aiotest_http_requests_total" in export

        await collector.stop()


@allure.feature("缓冲区管理")
class TestBufferManagement:
    """缓冲区管理相关的测试用例"""

    @allure.story("缓冲区")
    @allure.title("测试 Worker 节点缓冲区刷新")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_buffer_flush(self):
        """测试 Worker 节点的缓冲区刷新"""
        collector = MetricsCollector(
            node_type="worker",
            node_id="buffer-test",
            flush_interval=0.1
        )
        await collector.start()

        metrics = RequestMetrics(
            request_id="req-007",
            method="GET",
            endpoint="/api/buffer",
            status_code=200,
            duration=0.1,
            response_size=256
        )
        await collector.process_request_metrics(metrics=metrics)

        await asyncio.sleep(0.2)

        await collector.stop()

    @allure.story("缓冲区")
    @allure.title("测试缓冲区大小限制")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_buffer_size_limit(self):
        """测试缓冲区大小限制"""
        collector = MetricsCollector(
            node_type="worker",
            node_id="size-test",
            buffer_size=2,
            flush_interval=10.0
        )

        class MockCoordinator:
            async def publish(self, *args, **kwargs):
                pass

        collector.coordinator = MockCoordinator()
        await collector.start()

        for i in range(5):
            metrics = RequestMetrics(
                request_id=f"req-{i}",
                method="GET",
                endpoint="/api/limit",
                status_code=200,
                duration=0.1,
                response_size=256
            )
            await collector.process_request_metrics(metrics=metrics)

        assert len(collector._metrics_buffer) <= 2

        await collector.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
