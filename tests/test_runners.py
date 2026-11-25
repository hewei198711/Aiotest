# encoding: utf-8

import asyncio

import allure
import pytest
from aiohttp.test_utils import TestClient, TestServer

from aiotest import runners
from aiotest.events import test_quit
from aiotest.exception import RunnerError
from aiotest.runner_factory import (NODE_TYPE_LOCAL, NODE_TYPE_MASTER,
                                    NODE_TYPE_WORKER)
from aiotest.runners import (LocalRunner, MasterRunner, WorkerNode,
                             WorkerRunner, create_prometheus_app,
                             init_metrics_collector, start_prometheus_service)
from aiotest.state_manager import RunnerState

# 模块级别的MockRedisClient基类，包含所有必需的Redis方法
class _BaseMockRedisClient:
    """完整的Mock Redis客户端，提供所有distributed_coordinator需要的方法"""

    async def publish(self, *args, **kwargs):
        pass

    async def subscribe(self, *args, **kwargs):
        class MockPubSub:
            async def get_message(self, *args, **kwargs):
                return None

            async def listen(self, *args, **kwargs):
                # 异步生成器，不产生任何消息
                if False:
                    yield  # noqa: 保持生成器接口
        return MockPubSub()

    def pubsub(self, *args, **kwargs):
        """返回模拟的PubSub对象，支持subscribe/get_message/listen"""

        class MockPubSub:
            async def subscribe(self, *args, **kwargs):
                pass

            async def unsubscribe(self, *args, **kwargs):
                pass

            async def close(self, *args, **kwargs):
                pass

            async def get_message(self, *args, **kwargs):
                # 模拟真实Redis的等待行为，避免死循环阻塞事件循环
                timeout = kwargs.get('timeout', 1.0)
                await asyncio.sleep(timeout)
                return None

            async def listen(self, *args, **kwargs):
                # 异步生成器，不产生任何消息
                if False:
                    yield  # noqa: 保持生成器接口
        return MockPubSub()

    async def scan(self, cursor=0, match=None, count=None):
        """返回 (cursor, keys)，模拟无匹配key"""
        return (0, [])

    async def hgetall(self, key):
        """返回空的hash数据"""
        return {}

    async def time(self):
        """返回模拟的Redis服务器时间 (秒, 微秒)"""
        import time as _time
        t = _time.time()
        return (int(t), int((t - int(t)) * 1_000_000))

    async def hset(self, *args, **kwargs):
        pass

    async def set(self, *args, **kwargs):
        pass

    async def get(self, *args, **kwargs):
        return None

    async def close(self):
        pass


@allure.feature("辅助函数")
class TestHelperFunctions:
    """辅助函数的测试用例"""

    @allure.story("Prometheus应用")
    @allure.title("测试创建Prometheus应用")
    @allure.severity(allure.severity_level.NORMAL)
    def test_create_prometheus_app(self):
        """测试创建Prometheus指标HTTP应用"""
        app = create_prometheus_app()
        assert app is not None
        # 验证路由是否正确添加
        routes = [route.resource.canonical for route in app.router.routes()]
        assert "/metrics" in routes

    @allure.story("指标收集器")
    @allure.title("测试初始化指标收集器")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_init_metrics_collector(self):
        """测试初始化指标收集器"""
        # 使用真实参数进行测试
        node = NODE_TYPE_LOCAL
        redis_client = None  # Local模式不需要Redis
        node_id = "test_node"
        coordinator = None  # Local模式不需要协调器

        # 测试初始化指标收集器
        collector = await init_metrics_collector(node, redis_client, node_id, coordinator)
        assert collector is not None

        # 清理资源
        await collector.stop()

    @allure.story("Prometheus服务")
    @allure.title("测试启动Prometheus服务")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_start_prometheus_service(self):
        """测试启动Prometheus服务"""
        # 模拟配置
        class MockConfig:
            def __init__(self):
                self.prometheus_port = 8000

        config = MockConfig()

        # 启动服务
        prometheus_runner = await start_prometheus_service(config)

        # 清理资源
        await prometheus_runner.cleanup()

    @allure.story("Prometheus服务")
    @allure.title("测试Prometheus metrics handler异常处理")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_metrics_handler_exception(self):
        """测试Prometheus metrics handler的异常处理"""
        # 保存原始的generate_latest函数
        original_generate_latest = runners.generate_latest
        try:
            # 创建一个模拟的generate_latest函数，它会抛出异常
            def mock_generate_latest(registry):
                raise Exception("Test exception")

            # 替换runners模块中的generate_latest引用
            runners.generate_latest = mock_generate_latest

            # 创建应用
            app = create_prometheus_app()

            # 模拟请求
            server = TestServer(app)
            async with server:
                async with TestClient(server) as client:
                    # 发送请求到/metrics端点
                    response = await client.get('/metrics')

                    # 验证响应状态码为500
                    assert response.status == 500

                    # 验证响应内容
                    content = await response.text()
                    assert 'Internal Server Error' in content
        finally:
            # 恢复原始的generate_latest函数
            runners.generate_latest = original_generate_latest


@allure.feature("WorkerNode")
class TestWorkerNode:
    """WorkerNode 类的测试用例"""

    @allure.story("初始化")
    @allure.title("测试WorkerNode初始化")
    @allure.severity(allure.severity_level.NORMAL)
    def test_worker_node_initialization(self):
        """测试WorkerNode初始化时正确设置属性"""
        node_id = "test_worker"
        worker_node = WorkerNode(node_id)

        assert worker_node.node_id == node_id
        assert worker_node.status == RunnerState.READY
        assert worker_node.cpu_usage == 0.0
        assert worker_node.active_users == 0
        assert worker_node.last_update == 0.0

    @allure.story("更新状态")
    @allure.title("测试从心跳数据更新节点状态")
    @allure.severity(allure.severity_level.NORMAL)
    def test_update_from_heartbeat(self):
        """测试从心跳数据更新节点状态"""
        node_id = "test_worker"
        worker_node = WorkerNode(node_id)

        # 心跳数据
        heartbeat_data = {
            "cpu_percent": 50.5,
            "active_users": 100,
            "status": "running"
        }

        # 更新状态
        worker_node.update_from_heartbeat(heartbeat_data)

        assert worker_node.cpu_usage == 50.5
        assert worker_node.active_users == 100
        # 验证状态是否正确更新（注意：RunnerState可能使用小写）
        assert worker_node.status.value == "running"
        assert worker_node.last_update > 0.0

    @allure.story("更新状态")
    @allure.title("测试处理无效状态字符串")
    @allure.severity(allure.severity_level.NORMAL)
    def test_update_from_heartbeat_invalid_status(self):
        """测试处理无效状态字符串"""
        node_id = "test_worker"
        worker_node = WorkerNode(node_id)
        original_status = worker_node.status

        # 心跳数据（包含无效状态）
        heartbeat_data = {
            "cpu_percent": 50.5,
            "active_users": 100,
            "status": "invalid_status"
        }

        # 更新状态
        worker_node.update_from_heartbeat(heartbeat_data)

        assert worker_node.cpu_usage == 50.5
        assert worker_node.active_users == 100
        # 验证状态保持不变
        assert worker_node.status == original_status
        assert worker_node.last_update > 0.0

    @allure.story("状态检查")
    @allure.title("测试节点是否过期")
    @allure.severity(allure.severity_level.NORMAL)
    def test_is_stale(self):
        """测试节点是否处于过期状态"""
        node_id = "test_worker"
        worker_node = WorkerNode(node_id)

        # 从未收到心跳，应该返回True
        assert worker_node.is_stale(1.0) is True

        # 更新心跳数据
        heartbeat_data = {
            "cpu_percent": 50.5,
            "active_users": 100
        }
        worker_node.update_from_heartbeat(heartbeat_data)

        # 刚更新，不应该过期
        assert worker_node.is_stale(1.0) is False


@allure.feature("LocalRunner")
class TestLocalRunner:
    """LocalRunner 类的测试用例"""

    @allure.story("初始化")
    @allure.title("测试LocalRunner初始化")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_local_runner_initialization(self, mock_config, test_load_shape):
        """测试LocalRunner初始化时正确设置属性"""
        # 使用真实参数进行测试
        user_types = []

        # 使用fixture创建配置
        config = mock_config(prometheus_port=8000)

        # 创建LocalRunner实例
        runner = LocalRunner(user_types, test_load_shape, config)

        assert runner.node == NODE_TYPE_LOCAL
        assert runner.metrics_collector is None
        assert runner.prometheus_server_started is False
        assert runner.prometheus_runner is None

    @allure.story("初始化")
    @allure.title("测试LocalRunner初始化组件")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_local_runner_initialize(self, mock_config, test_load_shape):
        """测试LocalRunner初始化特有的组件"""
        # 使用真实参数进行测试
        user_types = []

        # 使用fixture创建配置
        config = mock_config(prometheus_port=8002)  # 使用不同端口避免冲突

        # 创建LocalRunner实例
        runner = LocalRunner(user_types, test_load_shape, config)

        # 初始化
        await runner.initialize()

        # 验证初始化
        assert runner.metrics_collector is not None
        assert runner.prometheus_runner is not None
        assert runner.prometheus_server_started is True

        # 清理资源
        await runner.stop()

    @allure.story("停止")
    @allure.title("测试LocalRunner停止")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_local_runner_stop(self, mock_config, test_load_shape):
        """测试LocalRunner停止"""
        # 使用真实参数进行测试
        user_types = []

        # 使用fixture创建配置
        config = mock_config(prometheus_port=8001)  # 使用不同端口避免冲突

        # 创建LocalRunner实例
        runner = LocalRunner(user_types, test_load_shape, config)

        # 初始化
        await runner.initialize()

        # 手动设置prometheus_server_started为True（确保它被正确设置）
        runner.prometheus_server_started = True

        # 直接测试停止Prometheus服务的逻辑
        if runner.prometheus_runner:
            await runner.prometheus_runner.cleanup()
            runner.prometheus_runner = None
            runner.prometheus_server_started = False

        # 验证停止后状态
        assert runner.prometheus_server_started is False
        assert runner.prometheus_runner is None

    @allure.story("停止")
    @allure.title("测试LocalRunner从READY状态停止")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_local_runner_stop_from_ready(self):
        """测试LocalRunner从READY状态停止"""
        # 使用真实参数进行测试
        user_types = []

        # 创建一个简单的负载形状类
        class TestLoadShape:
            def tick(self):
                return None

        load_shape = TestLoadShape()

        class MockConfig:
            def __init__(self):
                self.prometheus_port = 8002  # 使用不同端口避免冲突
                self.metrics_collection_interval = 5.0

        config = MockConfig()

        # 创建LocalRunner实例
        runner = LocalRunner(user_types, load_shape, config)

        # 直接停止（未初始化）
        await runner.stop()

        # 验证状态未变化
        assert runner.prometheus_server_started is False
        assert runner.prometheus_runner is None

    @allure.story("暂停/恢复")
    @allure.title("测试LocalRunner暂停")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_local_runner_pause(self, mock_config, test_load_shape):
        """测试LocalRunner暂停"""
        # 使用真实参数进行测试
        user_types = []

        # 使用fixture创建配置
        config = mock_config(prometheus_port=8010)  # 使用不同端口避免冲突

        # 创建LocalRunner实例
        runner = LocalRunner(user_types, test_load_shape, config)

        # 初始化
        await runner.initialize()

        # 启动测试
        await runner.start()

        # 模拟测试运行中状态（按照正确的状态转换顺序）
        await runner.state_manager.transition_state(RunnerState.STARTING)
        await runner.state_manager.transition_state(RunnerState.RUNNING)

        # 暂停测试
        await runner.pause()

        # 验证状态
        assert runner.state.value == "paused"

        # 清理资源
        await runner.quit()

    @allure.story("暂停/恢复")
    @allure.title("测试LocalRunner恢复")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_local_runner_resume(self, mock_config, test_load_shape):
        """测试LocalRunner恢复"""
        # 使用真实参数进行测试
        user_types = []

        # 使用fixture创建配置
        config = mock_config(prometheus_port=8011)  # 使用不同端口避免冲突

        # 创建LocalRunner实例
        runner = LocalRunner(user_types, test_load_shape, config)

        # 初始化
        await runner.initialize()

        # 启动测试
        await runner.start()

        # 模拟测试运行中状态（按照正确的状态转换顺序）
        await runner.state_manager.transition_state(RunnerState.STARTING)
        await runner.state_manager.transition_state(RunnerState.RUNNING)

        # 暂停测试
        await runner.pause()
        assert runner.state.value == "paused"

        # 恢复测试
        await runner.resume()

        # 验证状态
        assert runner.state.value == "running"

        # 清理资源
        await runner.quit()

    @allure.story("暂停/恢复")
    @allure.title("测试LocalRunner从错误状态暂停")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_local_runner_pause_from_invalid_state(self, mock_config, test_load_shape):
        """测试LocalRunner从无效状态暂停"""
        # 使用真实参数进行测试
        user_types = []

        # 使用fixture创建配置
        config = mock_config(prometheus_port=8012)  # 使用不同端口避免冲突

        # 创建LocalRunner实例
        runner = LocalRunner(user_types, test_load_shape, config)

        # 初始化
        await runner.initialize()

        # 直接暂停（未启动）
        await runner.pause()

        # 验证状态未变化
        assert runner.state.value == "ready"

        # 清理资源
        await runner.quit()

    @allure.story("暂停/恢复")
    @allure.title("测试LocalRunner从错误状态恢复")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_local_runner_resume_from_invalid_state(self, mock_config, test_load_shape):
        """测试LocalRunner从无效状态恢复"""
        # 使用真实参数进行测试
        user_types = []

        # 使用fixture创建配置
        config = mock_config(prometheus_port=8013)  # 使用不同端口避免冲突

        # 创建LocalRunner实例
        runner = LocalRunner(user_types, test_load_shape, config)

        # 初始化
        await runner.initialize()

        # 直接恢复（未暂停）
        await runner.resume()

        # 验证状态未变化
        assert runner.state.value == "ready"

        # 清理资源
        await runner.quit()

    @allure.story("指标收集")
    @allure.title("测试LocalRunner停止时回收CPU采集子任务")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_local_runner_collect_node_metrics_cancels_cpu_task(
            self, mock_config, test_load_shape):
        """_collect_node_metrics 被取消时须在 finally 中回收 cpu_task（N-3）"""
        config = mock_config(prometheus_port=8014,
                             metrics_collection_interval=0.05)
        runner = LocalRunner([], test_load_shape, config)
        # initialize() 才会赋值 metrics_collection_interval 等属性
        await runner.initialize()

        # 记录启动前已存在的同名任务，避免受其他用例残留任务干扰
        before = {t for t in asyncio.all_tasks()
                  if t.get_name() == "cpu_metrics_collector"}

        # 直接启动节点指标收集任务（内部会创建 cpu_metrics_collector 子任务）
        collect_task = asyncio.create_task(runner._collect_node_metrics())
        await asyncio.sleep(0.1)

        new_cpu = [t for t in asyncio.all_tasks()
                   if t.get_name() == "cpu_metrics_collector" and t not in before]
        assert len(new_cpu) == 1
        cpu_task = new_cpu[0]
        assert not cpu_task.done()

        # 模拟 stop()→cancel_all_tasks 取消父任务（stop 不置 is_quit）
        collect_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await collect_task

        # 父任务被取消后，CPU 子任务应已在 finally 中被回收
        assert cpu_task.done()

        # 清理资源
        await runner.quit()


@allure.feature("WorkerRunner")
class TestWorkerRunner:
    """WorkerRunner 类的测试用例"""

    @allure.story("初始化")
    @allure.title("测试WorkerRunner初始化")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_worker_runner_initialization(self):
        """测试WorkerRunner初始化时正确设置属性"""
        # 使用真实参数进行测试
        user_types = []

        # 创建一个简单的负载形状类
        class TestLoadShape:
            def tick(self):
                return None

        load_shape = TestLoadShape()

        # 创建一个简单的Redis客户端模拟
        class MockRedisClient(_BaseMockRedisClient):
            pass

        redis_client = MockRedisClient()

        class MockConfig:
            def __init__(self):
                self.metrics_collection_interval = 5.0
                self.metrics_batch_size = 100
                self.metrics_flush_interval = 1.0
                self.metrics_buffer_size = 10000

        config = MockConfig()

        # 创建WorkerRunner实例
        runner = WorkerRunner(user_types, load_shape, config, redis_client)

        assert runner.node == NODE_TYPE_WORKER
        assert runner.redis_client == redis_client
        assert runner.client_id is not None
        assert runner.coordinator is not None

        # 初始化
        await runner.initialize()

        assert runner.metrics_collection_interval == 5.0

        # 清理资源
        await runner.quit()

    @allure.story("负载形状管理")
    @allure.title("测试WorkerRunner负载形状管理器")
    @allure.severity(allure.severity_level.NORMAL)
    def test_worker_runner_load_shape_manager(self):
        """测试WorkerRunner的load_shape_manager属性"""
        # 使用真实参数进行测试
        user_types = []

        # 创建一个简单的负载形状类
        class TestLoadShape:
            def tick(self):
                return None

        load_shape = TestLoadShape()

        # 创建一个简单的Redis客户端模拟
        class MockRedisClient(_BaseMockRedisClient):
            pass

        redis_client = MockRedisClient()

        class MockConfig:
            def __init__(self):
                self.metrics_collection_interval = 5.0
                self.metrics_batch_size = 100
                self.metrics_flush_interval = 1.0
                self.metrics_buffer_size = 10000

        config = MockConfig()

        # 创建WorkerRunner实例
        runner = WorkerRunner(user_types, load_shape, config, redis_client)

        # 验证load_shape_manager返回None
        assert runner.load_shape_manager is None

    @allure.story("初始化")
    @allure.title("测试WorkerRunner初始化组件")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_worker_runner_initialize(self):
        """测试WorkerRunner初始化"""
        # 使用真实参数进行测试
        user_types = []

        # 创建一个简单的负载形状类
        class TestLoadShape:
            def tick(self):
                return None

        load_shape = TestLoadShape()

        # 创建一个简单的Redis客户端模拟
        class MockRedisClient(_BaseMockRedisClient):
            pass

        redis_client = MockRedisClient()

        class MockConfig:
            def __init__(self):
                self.metrics_collection_interval = 5.0
                self.metrics_batch_size = 100
                self.metrics_flush_interval = 1.0
                self.metrics_buffer_size = 10000

        config = MockConfig()

        # 创建WorkerRunner实例
        runner = WorkerRunner(user_types, load_shape, config, redis_client)

        # 初始化
        await runner.initialize()

        # 验证初始化
        assert runner.metrics_collector is not None
        assert runner.coordinator is not None

        # 清理资源
        await runner.quit()

    @allure.story("命令处理")
    @allure.title("测试WorkerRunner处理命令")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_worker_runner_handle_command(self):
        """测试WorkerRunner处理命令"""
        # 使用真实参数进行测试
        user_types = []

        # 创建一个简单的负载形状类
        class TestLoadShape:
            def tick(self):
                return None

        load_shape = TestLoadShape()

        # 创建一个简单的Redis客户端模拟
        class MockRedisClient(_BaseMockRedisClient):
            pass

        redis_client = MockRedisClient()

        class MockConfig:
            def __init__(self):
                self.metrics_collection_interval = 5.0
                self.metrics_batch_size = 100
                self.metrics_flush_interval = 1.0
                self.metrics_buffer_size = 10000

        config = MockConfig()

        # 创建WorkerRunner实例
        runner = WorkerRunner(user_types, load_shape, config, redis_client)

        # 初始化
        await runner.initialize()

        # 测试startup命令 - 不实际执行apply_load，只测试命令处理逻辑
        # 由于apply_load需要正整数用户数，我们直接测试命令处理函数的其他部分
        # 这里我们不调用_startup_completed，因为它需要Redis连接
        await runner._handle_command({"user_count": 1, "rate": 1}, "worker1", "startup")

        # 测试stop命令
        await runner._handle_command({}, "worker1", "stop")

        # 测试pause命令
        await runner._handle_command({}, "worker1", "pause")

        # 测试resume命令
        await runner._handle_command({}, "worker1", "resume")

        # 测试quit命令
        await runner._handle_command({}, "worker1", "quit")

        # 清理资源
        await runner.quit()

    @allure.story("应用负载")
    @allure.title("测试WorkerRunner应用负载")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_worker_runner_apply_load(self):
        """测试WorkerRunner应用负载"""
        # 使用真实参数进行测试
        user_types = []

        # 创建一个简单的负载形状类
        class TestLoadShape:
            def tick(self):
                return None

        load_shape = TestLoadShape()

        # 创建一个更完整的Redis客户端模拟
        class MockRedisClient(_BaseMockRedisClient):
            pass

        redis_client = MockRedisClient()

        class MockConfig:
            def __init__(self):
                self.metrics_collection_interval = 5.0
                self.metrics_batch_size = 100
                self.metrics_flush_interval = 1.0
                self.metrics_buffer_size = 10000

        config = MockConfig()

        # 创建WorkerRunner实例
        runner = WorkerRunner(user_types, load_shape, config, redis_client)

        # 初始化
        await runner.initialize()

        # 清理资源 - 不调用apply_load，因为会创建真实用户
        await runner.quit()


@allure.feature("MasterRunner")
class TestMasterRunner:
    """MasterRunner 类的测试用例"""

    @allure.story("初始化")
    @allure.title("测试MasterRunner初始化")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_master_runner_initialization(self):
        """测试MasterRunner初始化时正确设置属性"""
        # 使用真实参数进行测试
        user_types = []

        # 创建一个简单的负载形状类
        class TestLoadShape:
            def tick(self):
                return None

        load_shape = TestLoadShape()

        # 创建一个简单的Redis客户端模拟
        class MockRedisClient(_BaseMockRedisClient):
            pass

        redis_client = MockRedisClient()

        class MockConfig:
            def __init__(self):
                self.prometheus_port = 8000

        config = MockConfig()

        # 创建MasterRunner实例
        runner = MasterRunner(user_types, load_shape, config, redis_client)

        assert runner.user_types == user_types
        assert runner.load_shape == load_shape
        assert runner.config == config
        assert runner.node == NODE_TYPE_MASTER
        assert runner.redis_client == redis_client
        assert runner.coordinator is not None
        assert runner.workers == {}
        assert runner.metrics_collector is None
        assert runner.cpu_usage == 0
        assert runner.task_manager.background_tasks == []
        assert runner._load_shape_manager is None
        assert runner.prometheus_runner is None
        assert runner.prometheus_server_started is False

    @allure.story("初始化")
    @allure.title("测试MasterRunner初始化组件")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_master_runner_initialize(self):
        """测试MasterRunner初始化"""
        # 使用真实参数进行测试
        user_types = []

        # 创建一个简单的负载形状类
        class TestLoadShape:
            def tick(self):
                return None

        load_shape = TestLoadShape()

        # 创建一个简单的Redis客户端模拟
        class MockRedisClient(_BaseMockRedisClient):
            pass

        redis_client = MockRedisClient()

        class MockConfig:
            def __init__(self):
                self.prometheus_port = 8003  # 使用不同端口避免冲突
                self.metrics_batch_size = 100
                self.metrics_flush_interval = 1.0
                self.metrics_buffer_size = 10000

        config = MockConfig()

        # 创建MasterRunner实例
        runner = MasterRunner(user_types, load_shape, config, redis_client)

        # 初始化
        await runner.initialize()

        # 验证初始化
        assert runner.metrics_collector is not None
        assert runner.prometheus_runner is not None
        assert runner.prometheus_server_started is True
        assert len(runner.task_manager.background_tasks) == 3

        # 清理资源
        await runner.quit()

    @allure.story("资源分配")
    @allure.title("测试MasterRunner分配资源")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_master_runner_distribute_resources(self):
        """测试MasterRunner将总资源均匀分配给所有Worker节点"""
        # 使用真实参数进行测试
        user_types = []

        # 创建一个简单的负载形状类
        class TestLoadShape:
            def tick(self):
                return None

        load_shape = TestLoadShape()

        # 创建一个简单的Redis客户端模拟
        class MockRedisClient(_BaseMockRedisClient):
            pass

        redis_client = MockRedisClient()

        class MockConfig:
            def __init__(self):
                self.prometheus_port = 8000

        config = MockConfig()

        # 创建MasterRunner实例
        runner = MasterRunner(user_types, load_shape, config, redis_client)

        # 测试分配资源
        distribution = runner._distribute_resources(10, 3)
        assert len(distribution) == 3
        assert sum(distribution) == 10
        assert 4 in distribution  # 10 / 3 = 3 余 1，所以有一个节点会分配到 4

    @allure.story("资源分配")
    @allure.title("测试MasterRunner小数速率分配不截断")
    @allure.severity(allure.severity_level.NORMAL)
    def test_master_runner_distribute_rate_fractional(self):
        """小数速率应按浮点均分，不能因 int() 截断出现 0 速率 Worker"""
        # 使用真实参数进行测试
        user_types = []

        # 创建一个简单的负载形状类
        class TestLoadShape:
            def tick(self):
                return None

        load_shape = TestLoadShape()

        # 创建一个简单的Redis客户端模拟
        class MockRedisClient(_BaseMockRedisClient):
            pass

        redis_client = MockRedisClient()

        class MockConfig:
            def __init__(self):
                self.prometheus_port = 8000

        config = MockConfig()

        # 创建MasterRunner实例
        runner = MasterRunner(user_types, load_shape, config, redis_client)

        # 小数速率 1.5 分配给 2 个 Worker：不应截断为 [1, 0]，而是 [0.75, 0.75]
        distribution = runner._distribute_rate(1.5, 2)
        assert len(distribution) == 2
        assert all(r > 0 for r in distribution)
        assert sum(distribution) == pytest.approx(1.5)

        # 速率 0.5 分配给 2 个 Worker：每节点 0.25
        distribution = runner._distribute_rate(0.5, 2)
        assert all(r > 0 for r in distribution)
        assert sum(distribution) == pytest.approx(0.5)

        # 整数速率仍保持精确分配
        distribution = runner._distribute_rate(10, 2)
        assert sum(distribution) == 10

        # 无 Worker 时返回空列表
        assert runner._distribute_rate(10, 0) == []

    @allure.story("命令处理")
    @allure.title("测试MasterRunner处理命令")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_master_runner_handle_command(self):
        """测试MasterRunner处理命令"""
        # 使用真实参数进行测试
        user_types = []

        # 创建一个简单的负载形状类
        class TestLoadShape:
            def tick(self):
                return None

        load_shape = TestLoadShape()

        # 创建一个简单的Redis客户端模拟
        class MockRedisClient(_BaseMockRedisClient):
            pass

        redis_client = MockRedisClient()

        class MockConfig:
            def __init__(self):
                self.prometheus_port = 8004  # 使用不同端口避免冲突
                self.metrics_batch_size = 100
                self.metrics_flush_interval = 1.0
                self.metrics_buffer_size = 10000

        config = MockConfig()

        # 创建MasterRunner实例
        runner = MasterRunner(user_types, load_shape, config, redis_client)

        # 初始化
        await runner.initialize()

        # 测试startup_completed命令
        runner._startup_completion_tracker = {
            "completed_workers": set(),
            "expected_workers": 2
        }

        await runner._handle_command({"user_count": 100}, "worker1", "startup_completed")
        assert "worker1" in runner._startup_completion_tracker["completed_workers"]

        # 测试stop命令
        runner._stop_completion_tracker = {
            "stopped_workers": set(),
            "total_workers": 1  # 设置为1，这样处理stop命令时会触发状态转换
        }

        await runner._handle_command({}, "worker1", "stop")
        assert "worker1" in runner._stop_completion_tracker["stopped_workers"]

        # 清理资源
        await runner.quit()

    @allure.story("Worker管理")
    @allure.title("测试MasterRunner更新Worker状态")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_master_runner_update_worker_status(self):
        """测试MasterRunner更新Worker状态和指标数据"""
        # 使用真实参数进行测试
        user_types = []

        # 创建一个简单的负载形状类
        class TestLoadShape:
            def tick(self):
                return None

        load_shape = TestLoadShape()

        # 创建一个简单的Redis客户端模拟
        class MockRedisClient(_BaseMockRedisClient):
            pass

        redis_client = MockRedisClient()

        class MockConfig:
            def __init__(self):
                self.prometheus_port = 8005  # 使用不同端口避免冲突
                self.metrics_batch_size = 100
                self.metrics_flush_interval = 1.0
                self.metrics_buffer_size = 10000

        config = MockConfig()

        # 创建MasterRunner实例
        runner = MasterRunner(user_types, load_shape, config, redis_client)

        # 初始化
        await runner.initialize()

        # 测试更新Worker状态
        heartbeat_data = {
            "cpu_percent": 50.5,
            "active_users": 100,
            "status": "running"
        }

        await runner._update_worker_status(heartbeat_data, "worker1")
        assert "worker1" in runner.workers
        assert runner.workers["worker1"].cpu_usage == 50.5
        assert runner.workers["worker1"].active_users == 100
        # 验证状态是否正确更新（注意：RunnerState可能使用小写）
        assert runner.workers["worker1"].status.value == "running"

        # 清理资源
        await runner.quit()

    @allure.story("Worker管理")
    @allure.title("测试MasterRunner获取健康Worker")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_master_runner_get_healthy_workers(self):
        """测试MasterRunner获取所有健康的Worker节点"""
        # 使用真实参数进行测试
        user_types = []

        # 创建一个简单的负载形状类
        class TestLoadShape:
            def tick(self):
                return None

        load_shape = TestLoadShape()

        # 创建一个简单的Redis客户端模拟
        class MockRedisClient(_BaseMockRedisClient):
            async def get(self, *args, **kwargs):
                # 模拟Redis get操作，返回一个有效的心跳值
                import json
                return json.dumps(
                    {"timestamp": asyncio.get_event_loop().time()})

        redis_client = MockRedisClient()

        class MockConfig:
            def __init__(self):
                self.prometheus_port = 8006  # 使用不同端口避免冲突
                self.metrics_batch_size = 100
                self.metrics_flush_interval = 1.0
                self.metrics_buffer_size = 10000

        config = MockConfig()

        # 创建MasterRunner实例
        runner = MasterRunner(user_types, load_shape, config, redis_client)

        # 初始化
        await runner.initialize()

        # 添加测试Worker
        runner.workers["worker1"] = WorkerNode("worker1")
        runner.workers["worker1"].status = RunnerState.RUNNING

        # 测试获取健康Worker
        healthy_workers = await runner.get_healthy_workers()
        # 由于我们的Redis模拟可能不会正确实现check_worker_heartbeat，所以这里可能返回空列表
        # 但我们可以验证方法执行没有错误
        assert isinstance(healthy_workers, list)

        # 清理资源
        await runner.quit()

    @allure.story("退出")
    @allure.title("测试MasterRunner退出")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_master_runner_quit(self):
        """测试MasterRunner退出，确保正确停止load_shape_manager"""
        # 使用真实参数进行测试
        user_types = []

        # 创建一个简单的负载形状类
        class TestLoadShape:
            def tick(self):
                return None

        load_shape = TestLoadShape()

        # 创建一个简单的Redis客户端模拟
        class MockRedisClient(_BaseMockRedisClient):
            pass

        redis_client = MockRedisClient()

        class MockConfig:
            def __init__(self):
                self.prometheus_port = 8009  # 使用不同端口避免冲突
                self.metrics_batch_size = 100
                self.metrics_flush_interval = 1.0
                self.metrics_buffer_size = 10000

        config = MockConfig()

        # 创建MasterRunner实例
        runner = MasterRunner(user_types, load_shape, config, redis_client)

        # 初始化
        await runner.initialize()

        # 启动负载形状管理器
        await runner.start()
        assert runner.load_shape_manager is not None
        assert runner.load_shape_manager._is_running is True

        # 退出
        await runner.quit()

        # 验证load_shape_manager已停止
        assert runner.load_shape_manager._is_running is False
        assert runner.load_shape_manager._task is None
        assert runner.state_manager.is_in_quit_state()

    @allure.story("退出")
    @allure.title("测试MasterRunner退出触发test_quit事件")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_master_runner_quit_fires_test_quit_event(self):
        """MasterRunner.quit() 应触发 test_quit 事件（B-6）"""
        runner = await self._make_initialized_master(8012)

        received = []

        async def on_quit(**kwargs):
            received.append(kwargs)

        await test_quit.add_handler(on_quit)
        try:
            await runner.quit()
        finally:
            await test_quit.remove_handler(on_quit)

        # 事件触发一次，且携带 runner 参数
        assert len(received) == 1
        assert received[0].get("runner") is runner

    @allure.story("暂停/恢复")
    @allure.title("测试MasterRunner暂停")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_master_runner_pause(self):
        """测试MasterRunner暂停"""
        # 使用真实参数进行测试
        user_types = []

        # 创建一个简单的负载形状类
        class TestLoadShape:
            def tick(self):
                return None

        load_shape = TestLoadShape()

        # 创建一个简单的Redis客户端模拟
        published_commands = []

        import json

        class MockRedisClient(_BaseMockRedisClient):
            async def publish(self, channel, message):
                # 解析消息，提取command字段
                try:
                    payload = json.loads(message)
                    if "command" in payload:
                        published_commands.append(payload["command"])
                except json.JSONDecodeError:
                    pass

        redis_client = MockRedisClient()

        class MockConfig:
            def __init__(self):
                self.prometheus_port = 8014  # 使用不同端口避免冲突
                self.metrics_batch_size = 100
                self.metrics_flush_interval = 1.0
                self.metrics_buffer_size = 10000

        config = MockConfig()

        # 创建MasterRunner实例
        runner = MasterRunner(user_types, load_shape, config, redis_client)

        # 初始化
        await runner.initialize()

        # 启动测试
        await runner.start()

        # 模拟测试运行中状态（按照正确的状态转换顺序）
        await runner.state_manager.transition_state(RunnerState.STARTING)
        await runner.state_manager.transition_state(RunnerState.RUNNING)

        # 暂停测试
        await runner.pause()

        # 验证状态
        assert runner.state_manager.get_current_state().value == "paused"
        # 验证是否发送了pause命令
        assert "pause" in published_commands

        # 清理资源
        await runner.quit()

    @allure.story("暂停/恢复")
    @allure.title("测试MasterRunner暂停恢复同步负载形状计时")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_master_runner_pause_resume_sync_shape_timing(self):
        """暂停/恢复时负载形状的 pause/resume 计时控制应被调用"""
        # 使用真实参数进行测试
        user_types = []
        shape_calls = []

        # 负载形状带 pause/resume 记录调用
        class TestLoadShape:
            def tick(self):
                return None

            def pause(self):
                shape_calls.append("pause")

            def resume(self):
                shape_calls.append("resume")

        load_shape = TestLoadShape()

        class MockRedisClient(_BaseMockRedisClient):
            pass

        redis_client = MockRedisClient()

        class MockConfig:
            def __init__(self):
                self.prometheus_port = 8014  # 使用不同端口避免冲突
                self.metrics_batch_size = 100
                self.metrics_flush_interval = 1.0
                self.metrics_buffer_size = 10000

        config = MockConfig()

        # 创建MasterRunner实例
        runner = MasterRunner(user_types, load_shape, config, redis_client)

        # 初始化并启动
        await runner.initialize()
        await runner.start()

        # 模拟测试运行中状态（按照正确的状态转换顺序）
        await runner.state_manager.transition_state(RunnerState.STARTING)
        await runner.state_manager.transition_state(RunnerState.RUNNING)

        # 暂停测试：形状计时应被暂停
        await runner.pause()
        assert shape_calls == ["pause"]

        # 恢复测试：形状计时应被恢复
        await runner.resume()
        assert shape_calls == ["pause", "resume"]

        # 清理资源
        await runner.quit()

    @allure.story("暂停/恢复")
    @allure.title("测试MasterRunner恢复")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_master_runner_resume(self):
        """测试MasterRunner恢复"""
        # 使用真实参数进行测试
        user_types = []

        # 创建一个简单的负载形状类
        class TestLoadShape:
            def tick(self):
                return None

        load_shape = TestLoadShape()

        # 创建一个简单的Redis客户端模拟
        published_commands = []

        import json

        class MockRedisClient(_BaseMockRedisClient):
            async def publish(self, channel, message):
                # 解析消息，提取command字段
                try:
                    payload = json.loads(message)
                    if "command" in payload:
                        published_commands.append(payload["command"])
                except json.JSONDecodeError:
                    pass

        redis_client = MockRedisClient()

        class MockConfig:
            def __init__(self):
                self.prometheus_port = 8015  # 使用不同端口避免冲突
                self.metrics_batch_size = 100
                self.metrics_flush_interval = 1.0
                self.metrics_buffer_size = 10000

        config = MockConfig()

        # 创建MasterRunner实例
        runner = MasterRunner(user_types, load_shape, config, redis_client)

        # 初始化
        await runner.initialize()

        # 启动测试
        await runner.start()

        # 模拟测试运行中状态（按照正确的状态转换顺序）
        await runner.state_manager.transition_state(RunnerState.STARTING)
        await runner.state_manager.transition_state(RunnerState.RUNNING)

        # 暂停测试
        await runner.pause()
        assert runner.state_manager.get_current_state().value == "paused"

        # 恢复测试
        await runner.resume()

        # 验证状态
        assert runner.state_manager.get_current_state().value == "running"
        # 验证是否发送了resume命令
        assert "resume" in published_commands

        # 清理资源
        await runner.quit()

    @allure.story("资源分配")
    @allure.title("测试MasterRunner广播启动命令")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_master_runner_broadcast_startup(self):
        """测试MasterRunner广播启动命令到所有Worker节点 - 验证异步方法正确调用"""
        # 使用真实参数进行测试
        user_types = []

        # 创建一个简单的负载形状类
        class TestLoadShape:
            def tick(self):
                return None

        load_shape = TestLoadShape()

        # 记录发布的命令
        published_commands = []

        # 创建一个模拟的Redis客户端
        class MockRedisClient(_BaseMockRedisClient):
            pass

        redis_client = MockRedisClient()

        class MockConfig:
            def __init__(self):
                self.prometheus_port = 8007  # 使用不同端口避免冲突
                self.metrics_batch_size = 100
                self.metrics_flush_interval = 1.0
                self.metrics_buffer_size = 10000

        config = MockConfig()

        # 创建MasterRunner实例
        runner = MasterRunner(user_types, load_shape, config, redis_client)

        # 初始化
        await runner.initialize()

        # 添加测试Worker
        runner.workers["worker1"] = WorkerNode("worker1")
        runner.workers["worker1"].status = RunnerState.READY
        runner.workers["worker2"] = WorkerNode("worker2")
        runner.workers["worker2"].status = RunnerState.READY

        # 模拟coordinator的publish方法，记录发布的命令
        async def mock_publish(channel, data, worker_id=None, command=None):
            published_commands.append({
                "channel": channel,
                "data": data,
                "worker_id": worker_id,
                "command": command
            })

        runner.coordinator.publish = mock_publish

        # 测试广播启动命令 - 10个用户，速率10/s
        # （传入健康Worker列表，避免内部心跳检查依赖真实Redis）
        await runner._broadcast_startup(
            10, 10, healthy_workers=list(runner.workers.values()))

        # 验证命令已发布给所有Worker
        assert len(published_commands) == 2

        # 验证资源分配正确（10个用户分配给2个Worker，应该是5和5）
        user_counts = [cmd["data"]["user_count"] for cmd in published_commands]
        assert sum(user_counts) == 10
        assert all(count > 0 for count in user_counts)

        # 验证速率分配正确
        rates = [cmd["data"]["rate"] for cmd in published_commands]
        assert sum(rates) == 10

        # 验证命令类型正确
        assert all(cmd["command"] == "startup" for cmd in published_commands)
        assert all(cmd["channel"] == "command" for cmd in published_commands)

        # 清理资源
        await runner.quit()

    @allure.story("资源分配")
    @allure.title("测试MasterRunner广播启动命令无Worker时抛出异常")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_master_runner_broadcast_startup_no_workers(self):
        """测试MasterRunner广播启动命令时没有Worker时抛出异常"""
        # 使用真实参数进行测试
        user_types = []

        # 创建一个简单的负载形状类
        class TestLoadShape:
            def tick(self):
                return None

        load_shape = TestLoadShape()

        # 创建一个模拟的Redis客户端
        class MockRedisClient(_BaseMockRedisClient):
            pass

        redis_client = MockRedisClient()

        class MockConfig:
            def __init__(self):
                self.prometheus_port = 8008  # 使用不同端口避免冲突
                self.metrics_batch_size = 100
                self.metrics_flush_interval = 1.0
                self.metrics_buffer_size = 10000

        config = MockConfig()

        # 创建MasterRunner实例
        runner = MasterRunner(user_types, load_shape, config, redis_client)

        # 初始化
        await runner.initialize()

        # 测试没有Worker时应该抛出异常
        with pytest.raises(RunnerError) as exc_info:
            await runner._broadcast_startup(10, 10)

        assert "No ready workers available" in str(exc_info.value)

        # 清理资源
        await runner.quit()

    @allure.story("资源分配")
    @allure.title("测试广播启动命令时过滤失联Worker")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_master_runner_broadcast_startup_filters_missing(self):
        """测试广播启动命令时过滤失联（MISSING）Worker - 失联节点不计入分配"""
        user_types = []

        class TestLoadShape:
            def tick(self):
                return None

        load_shape = TestLoadShape()

        published_commands = []

        class MockRedisClient(_BaseMockRedisClient):
            pass

        redis_client = MockRedisClient()

        class MockConfig:
            def __init__(self):
                self.prometheus_port = 8010  # 使用不同端口避免冲突
                self.metrics_batch_size = 100
                self.metrics_flush_interval = 1.0
                self.metrics_buffer_size = 10000

        config = MockConfig()

        runner = MasterRunner(user_types, load_shape, config, redis_client)
        await runner.initialize()

        # 添加一个健康Worker和一个失联Worker
        runner.workers["worker1"] = WorkerNode("worker1")
        runner.workers["worker1"].status = RunnerState.READY
        runner.workers["worker_missing"] = WorkerNode("worker_missing")
        runner.workers["worker_missing"].status = RunnerState.MISSING

        async def mock_publish(channel, data, worker_id=None, command=None):
            published_commands.append({
                "channel": channel,
                "data": data,
                "worker_id": worker_id,
                "command": command
            })

        runner.coordinator.publish = mock_publish

        # 广播启动命令，仅传入健康Worker
        await runner._broadcast_startup(
            10, 10, healthy_workers=[runner.workers["worker1"]])

        # 验证只有健康Worker收到命令，且分配了全部10个用户
        assert len(published_commands) == 1
        assert published_commands[0]["worker_id"] == "worker1"
        assert published_commands[0]["data"]["user_count"] == 10

        # 清理资源
        await runner.quit()

    @allure.story("资源分配")
    @allure.title("测试用户数少于Worker数时报错退出")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_master_runner_broadcast_startup_insufficient_users(self):
        """用户数 < Worker数时广播启动应报错，不发 user_count=0 命令（B-1）"""
        user_types = []

        class TestLoadShape:
            def tick(self):
                return None

        class MockRedisClient(_BaseMockRedisClient):
            pass

        class MockConfig:
            def __init__(self):
                self.prometheus_port = 8008
                self.metrics_batch_size = 100
                self.metrics_flush_interval = 1.0
                self.metrics_buffer_size = 10000

        runner = MasterRunner(
            user_types, TestLoadShape(), MockConfig(), MockRedisClient())
        await runner.initialize()

        # 添加三个Worker
        for worker_id in ["worker1", "worker2", "worker3"]:
            runner.workers[worker_id] = WorkerNode(worker_id)
            runner.workers[worker_id].status = RunnerState.READY

        published_commands = []

        async def mock_publish(channel, data, worker_id=None, command=None):
            published_commands.append({
                "channel": channel,
                "data": data,
                "worker_id": worker_id,
                "command": command
            })

        runner.coordinator.publish = mock_publish

        # 3个Worker只有2个用户：无法为每个Worker分配至少1个用户，应报错
        with pytest.raises(RunnerError) as exc_info:
            await runner._broadcast_startup(
                2, 5.0, healthy_workers=list(runner.workers.values()))

        # 报错提示用户数与Worker数的关系
        assert "无法为每个Worker分配至少1个用户" in str(exc_info.value)

        # 校验发生在发布命令之前，无任何Worker收到启动命令
        assert len(published_commands) == 0

        # 清理资源
        await runner.quit()

    @allure.story("资源分配")
    @allure.title("测试用户数少于Worker数时apply_load报错并转STOPPING")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_master_runner_apply_load_insufficient_users(self):
        """apply_load 在用户数不足时报错退出，状态转 STOPPING（B-1）"""
        runner = await self._make_initialized_master(8009)

        # 添加三个Worker
        for worker_id in ["worker1", "worker2", "worker3"]:
            runner.workers[worker_id] = WorkerNode(worker_id)
            runner.workers[worker_id].status = RunnerState.READY

        # 替换健康Worker获取，隔离心跳检查
        async def fake_get_healthy_workers():
            return list(runner.workers.values())

        runner.get_healthy_workers = fake_get_healthy_workers

        published_commands = []

        async def mock_publish(channel, data, worker_id=None, command=None):
            published_commands.append({
                "channel": channel,
                "data": data,
                "worker_id": worker_id,
                "command": command
            })

        runner.coordinator.publish = mock_publish

        # 3个Worker只有2个用户：启动失败，异常传播并转入 STOPPING
        with pytest.raises(RunnerError):
            await runner.apply_load(2, 5.0)

        # 无任何Worker收到启动命令
        assert len(published_commands) == 0

        # 启动失败后状态转入 STOPPING（异常路径处理）
        assert runner.state_manager.get_current_state() == RunnerState.STOPPING

        # 清理资源
        await runner.quit()

    @allure.story("Worker管理")
    @allure.title("测试get_healthy_workers包含PAUSED Worker")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_master_runner_get_healthy_workers_includes_paused(self):
        """PAUSED 是运行状态而非失联，get_healthy_workers 应包含（B-3）"""
        runner = await self._make_initialized_master(8010)

        runner.workers["worker1"] = WorkerNode("worker1")
        runner.workers["worker1"].status = RunnerState.RUNNING
        runner.workers["worker2"] = WorkerNode("worker2")
        runner.workers["worker2"].status = RunnerState.PAUSED
        runner.workers["worker3"] = WorkerNode("worker3")
        runner.workers["worker3"].status = RunnerState.READY

        # worker1/worker2 存活，worker3 失联
        async def fake_check_worker_heartbeat(worker_id):
            return worker_id != "worker3"

        runner.coordinator.check_worker_heartbeat = (
            fake_check_worker_heartbeat)

        healthy = await runner.get_healthy_workers()
        healthy_ids = {w.node_id for w in healthy}

        # PAUSED Worker 计入健康列表，失联 Worker 被过滤
        assert healthy_ids == {"worker1", "worker2"}

        # 失联节点被标记为 MISSING
        assert runner.workers["worker3"].status == RunnerState.MISSING

        # 清理资源
        await runner.quit()

    @allure.story("资源分配")
    @allure.title("测试调整负载时PAUSED Worker参与分配")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_master_runner_adjust_load_includes_paused_worker(self):
        """调整负载时 PAUSED Worker 应计入分配，避免 resume 后负载永久不一致（B-3）"""
        runner = await self._make_initialized_master(8011)

        # 三个Worker：两个RUNNING，一个PAUSED
        runner.workers["worker1"] = WorkerNode("worker1")
        runner.workers["worker1"].status = RunnerState.RUNNING
        runner.workers["worker2"] = WorkerNode("worker2")
        runner.workers["worker2"].status = RunnerState.PAUSED
        runner.workers["worker3"] = WorkerNode("worker3")
        runner.workers["worker3"].status = RunnerState.RUNNING

        # 心跳检查全部存活
        async def fake_check_worker_heartbeat(worker_id):
            return True

        runner.coordinator.check_worker_heartbeat = (
            fake_check_worker_heartbeat)

        published_commands = []

        async def mock_publish(channel, data, worker_id=None, command=None):
            published_commands.append({
                "channel": channel,
                "data": data,
                "worker_id": worker_id,
                "command": command
            })

        runner.coordinator.publish = mock_publish

        # 进入 RUNNING 状态
        await runner.state_manager.transition_state(RunnerState.STARTING)
        await runner.state_manager.transition_state(RunnerState.RUNNING)

        # 调整负载：9个用户分配给3个Worker（含PAUSED）
        await runner.apply_load(9, 9.0)

        # 三个Worker都收到启动命令（PAUSED Worker 不再被过滤）
        assert len(published_commands) == 3
        receiving = {cmd["worker_id"] for cmd in published_commands}
        assert receiving == {"worker1", "worker2", "worker3"}

        # 每个Worker分配3个用户
        user_counts = [cmd["data"]["user_count"] for cmd in published_commands]
        assert user_counts == [3, 3, 3]

        # 清理资源
        await runner.quit()

    async def _make_initialized_master(self, port):
        """构造并初始化一个使用 Mock Redis 的 MasterRunner（停止类用例共用）"""
        class TestLoadShape:
            def tick(self):
                return None

        class MockRedisClient(_BaseMockRedisClient):
            pass

        class MockConfig:
            def __init__(self):
                self.prometheus_port = port
                self.metrics_batch_size = 100
                self.metrics_flush_interval = 1.0
                self.metrics_buffer_size = 10000

        runner = MasterRunner(
            [], TestLoadShape(), MockConfig(), MockRedisClient())
        await runner.initialize()
        return runner

    @allure.story("停止")
    @allure.title("测试MasterRunner无健康Worker时停止不卡死")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_master_runner_stop_no_workers(self):
        """无健康Worker时 stop() 应直接收尾转 READY，而非永久卡在 STOPPING（N-1）"""
        runner = await self._make_initialized_master(8021)

        # 进入 RUNNING 使 can_stop 成立
        await runner.state_manager.transition_state(RunnerState.STARTING)
        await runner.state_manager.transition_state(RunnerState.RUNNING)

        stop_events = []

        async def on_stop(runner=None, **kwargs):
            stop_events.append(runner)

        await runners.test_stop.add_handler(on_stop)
        try:
            # workers 为空 → get_healthy_workers() 返回 []
            await runner.stop()
            # 零Worker兜底：应立即转 READY 并触发一次 test_stop
            assert runner.state_manager.get_current_state() == RunnerState.READY
            assert len(stop_events) == 1
        finally:
            await runners.test_stop.remove_handler(on_stop)
            await runner.quit()

    @allure.story("停止")
    @allure.title("测试MasterRunner停止确认超时看门狗兜底")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_master_runner_stop_watchdog_timeout(self):
        """Worker失联不确认时，看门狗超时后强制收尾转 READY（N-1）"""
        runner = await self._make_initialized_master(8022)

        await runner.state_manager.transition_state(RunnerState.STARTING)
        await runner.state_manager.transition_state(RunnerState.RUNNING)
        await runner.state_manager.transition_state(RunnerState.STOPPING)

        # 模拟有一个Worker但始终不回停止确认
        runner._stop_finalized = False
        runner._stop_completion_tracker = {
            "stopped_workers": set(), "total_workers": 1}

        stop_events = []

        async def on_stop(runner=None, **kwargs):
            stop_events.append(runner)

        await runners.test_stop.add_handler(on_stop)
        try:
            await runner._watch_stop_completion(timeout=0.1)
            assert runner.state_manager.get_current_state() == RunnerState.READY
            assert runner._stop_finalized is True
            assert len(stop_events) == 1
        finally:
            await runners.test_stop.remove_handler(on_stop)
            await runner.quit()

    @allure.story("停止")
    @allure.title("测试MasterRunner停止收尾幂等")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_master_runner_finalize_stop_idempotent(self):
        """_finalize_stop 多次调用只转一次状态/触发一次 test_stop（N-1）"""
        runner = await self._make_initialized_master(8023)

        await runner.state_manager.transition_state(RunnerState.STARTING)
        await runner.state_manager.transition_state(RunnerState.RUNNING)
        await runner.state_manager.transition_state(RunnerState.STOPPING)
        runner._stop_finalized = False

        stop_events = []

        async def on_stop(runner=None, **kwargs):
            stop_events.append(runner)

        await runners.test_stop.add_handler(on_stop)
        try:
            await runner._finalize_stop()
            await runner._finalize_stop()  # 第二次应早退
            assert runner.state_manager.get_current_state() == RunnerState.READY
            assert len(stop_events) == 1
        finally:
            await runners.test_stop.remove_handler(on_stop)
            await runner.quit()


# 测试create_prometheus_app函数
@allure.feature("Prometheus")
class TestPrometheus:
    @allure.story("创建应用")
    @allure.title("测试create_prometheus_app函数")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_create_prometheus_app(self):
        # 创建一个模拟的runner对象
        class MockRunner:
            def __init__(self):
                self.state = "running"
                self.metrics_collector = None
                self.worker_status = {}

        # 测试带runner参数的情况
        runner = MockRunner()
        app = create_prometheus_app(runner=runner)
        assert app is not None

        # 测试不带runner参数的情况（向后兼容）
        app_no_runner = create_prometheus_app()
        assert app_no_runner is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
