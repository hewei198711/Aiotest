# encoding: utf-8

import asyncio
import logging

import allure
import pytest

from aiotest.exception import InvalidRateError, InvalidUserCountError
from aiotest.metrics import MetricsCollector
from aiotest.runner_factory import (NODE_TYPE_LOCAL, NODE_TYPE_MASTER,
                                    NODE_TYPE_WORKER, BaseRunner,
                                    EventHandlerRegistry, RunnerFactory,
                                    on_startup_completed,
                                    on_worker_request_metrics,
                                    validate_load_params, validate_params)
from aiotest.shape import LoadUserShape
from aiotest.state_manager import RunnerState
from aiotest.users import User


# 测试用的用户类
class TestUser(User):
    """测试用的用户类"""

    async def test_task(self):
        pass


# 测试用的负载形状类
class TestLoadShape(LoadUserShape):
    """测试用的负载形状类"""

    def tick(self):
        return (10, 1.0)


@allure.feature("参数验证")
class TestValidateLoadParams:
    """验证负载参数函数的测试用例"""

    @allure.story("有效参数")
    @allure.title("测试有效的用户数和速率")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.parametrize("user_count,rate", [
        (1, 1.0),
        (10, 5.0),
        (100, 50.0),
        (100, 100.0),
    ])
    def test_valid_params(self, user_count, rate):
        """测试有效的用户数和速率组合"""
        validate_load_params(user_count, rate)

    @allure.story("无效参数")
    @allure.title("测试无效的用户数")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.parametrize("user_count", [0, -1, -10])
    def test_invalid_user_count(self, user_count):
        """测试无效的用户数应该抛出 InvalidUserCountError"""
        with pytest.raises(InvalidUserCountError):
            validate_load_params(user_count, 1.0)

    @allure.story("无效参数")
    @allure.title("测试非整数用户数")
    @allure.severity(allure.severity_level.NORMAL)
    def test_non_integer_user_count(self):
        """测试非整数用户数应该抛出 InvalidUserCountError"""
        with pytest.raises(InvalidUserCountError):
            validate_load_params(10.5, 1.0)

    @allure.story("无效参数")
    @allure.title("测试无效的速率")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.parametrize("rate", [0, -1, 11])
    def test_invalid_rate(self, rate):
        """测试无效的速率应该抛出 InvalidRateError"""
        with pytest.raises(InvalidRateError):
            validate_load_params(10, rate)


@allure.feature("参数验证装饰器")
class TestValidateParams:
    """参数验证装饰器的测试用例"""

    @allure.story("装饰器功能")
    @allure.title("测试装饰器验证参数")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_validate_params_decorator(self):
        """测试装饰器正确验证参数"""
        class TestClass:
            @validate_params
            async def test_method(self, user_count, rate, extra_arg):
                return (user_count, rate, extra_arg)

        obj = TestClass()

        result = await obj.test_method(10, 5.0, "extra")
        assert result == (10, 5.0, "extra")

        with pytest.raises(InvalidUserCountError):
            await obj.test_method(0, 5.0, "extra")


@allure.feature("事件处理器注册")
class TestEventHandlerRegistry:
    """事件处理器注册中心的测试用例"""

    @allure.story("注册功能")
    @allure.title("测试事件处理器注册")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_register_handlers(self):
        """测试事件处理器注册功能"""
        registry = EventHandlerRegistry()

        class MockRunner:
            node = NODE_TYPE_LOCAL

        runner = MockRunner()
        await registry.register_handlers(runner)

        assert id(runner) in registry._registered_handlers

    @allure.story("重复注册")
    @allure.title("测试重复注册处理")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_duplicate_registration(self):
        """测试重复注册不会出错"""
        registry = EventHandlerRegistry()

        class MockRunner:
            node = NODE_TYPE_LOCAL

        runner = MockRunner()
        await registry.register_handlers(runner)
        await registry.register_handlers(runner)

        assert len(registry._registered_handlers) == 1


@allure.feature("基础运行器")
class TestBaseRunner:
    """基础运行器的测试用例"""

    @allure.story("初始化")
    @allure.title("测试基础运行器初始化")
    @allure.severity(allure.severity_level.NORMAL)
    def test_base_runner_initialization(self, base_config):
        """测试基础运行器正确初始化"""
        load_shape = TestLoadShape()
        runner = BaseRunner([TestUser], load_shape, base_config)

        assert runner.user_types == [TestUser]
        assert runner.load_shape == load_shape
        assert runner.config == base_config
        assert runner.node is None
        assert runner.cpu_usage == 0

    @allure.story("属性延迟加载")
    @allure.title("测试组件延迟初始化")
    @allure.severity(allure.severity_level.NORMAL)
    def test_lazy_initialization(self, base_config):
        """测试组件的延迟初始化"""
        load_shape = TestLoadShape()
        runner = BaseRunner([TestUser], load_shape, base_config)

        assert runner._user_manager is None
        assert runner._state_manager is None
        assert runner._task_manager is None
        assert runner._load_shape_manager is None

        assert runner.user_manager is not None
        assert runner.state_manager is not None
        assert runner.task_manager is not None

    @allure.story("属性访问")
    @allure.title("测试活跃用户数量属性")
    @allure.severity(allure.severity_level.NORMAL)
    def test_active_user_count_property(self, base_config):
        """测试活跃用户数量属性"""
        load_shape = TestLoadShape()
        runner = BaseRunner([TestUser], load_shape, base_config)

        count = runner.active_user_count
        assert isinstance(count, int)
        assert count >= 0

    @allure.story("属性访问")
    @allure.title("测试状态属性")
    @allure.severity(allure.severity_level.NORMAL)
    def test_state_property(self, base_config):
        """测试状态属性"""
        load_shape = TestLoadShape()
        runner = BaseRunner([TestUser], load_shape, base_config)

        state = runner.state
        assert state is not None


@allure.feature("事件处理器")
class TestEventHandlers:
    """事件处理函数的测试用例"""

    @allure.story("启动完成")
    @allure.title("测试本地运行器启动完成处理")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_on_startup_completed_local(self):
        """测试本地运行器的启动完成事件处理"""
        from aiotest.state_manager import StateManager

        class MockRunner:
            node = NODE_TYPE_LOCAL
            active_user_count = 10

            def __init__(self):
                self.state_manager = StateManager()

        runner = MockRunner()
        # 先转换到 STARTING 状态，然后才能转换到 RUNNING
        await runner.state_manager.transition_state(RunnerState.STARTING)

        await on_startup_completed(
            node_type=NODE_TYPE_LOCAL,
            runner=runner
        )

    @allure.story("启动完成")
    @allure.title("测试Master启动完成处理")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_on_startup_completed_master(self):
        """测试Master运行器的启动完成事件处理"""
        from aiotest.state_manager import StateManager

        class MockRunner:
            node = NODE_TYPE_MASTER
            _startup_completion_tracker = {
                "startup_data": {"user_count": 100},
                "completed_workers": {"worker1", "worker2"},
                "expected_workers": 2
            }

            def __init__(self):
                self.state_manager = StateManager()

        runner = MockRunner()
        # 先转换到 STARTING 状态，然后才能转换到 RUNNING
        await runner.state_manager.transition_state(RunnerState.STARTING)

        await on_startup_completed(
            node_type=NODE_TYPE_MASTER,
            runner=runner
        )

    @allure.story("指标处理")
    @allure.title("测试Worker请求指标处理")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_on_worker_request_metrics(self):
        """测试Worker请求指标处理"""
        class MockRunner:
            node = NODE_TYPE_MASTER

            def __init__(self):
                self.metrics_collector = MetricsCollector()

        runner = MockRunner()

        metrics_data = {
            "request_id": "test-123",
            "method": "GET",
            "endpoint": "/test",
            "status_code": 200,
            "duration": 0.1,
            "response_size": 100
        }

        await on_worker_request_metrics(
            node_type=NODE_TYPE_MASTER,
            runner=runner,
            data=metrics_data
        )

    @allure.story("指标处理")
    @allure.title("测试非Master节点忽略指标")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_on_worker_request_metrics_non_master(self):
        """测试非Master节点忽略Worker请求指标"""
        class MockRunner:
            node = NODE_TYPE_WORKER

        runner = MockRunner()

        await on_worker_request_metrics(
            node_type=NODE_TYPE_WORKER,
            runner=runner,
            data={"test": "data"}
        )


@allure.feature("运行器工厂")
class TestRunnerFactory:
    """运行器工厂的测试用例"""

    @allure.story("创建运行器")
    @allure.title("测试创建本地运行器")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_create_local_runner(self, base_config):
        """测试创建本地运行器"""
        load_shape = TestLoadShape()
        config = type('Config', (), {
            'host': 'http://localhost:8080',
            'timeout': 30,
            'prometheus_port': 9090,
            'metrics_collection_interval': 5.0,
            'metrics_batch_size': 100,
            'metrics_flush_interval': 1.0,
            'metrics_buffer_size': 10000
        })()

        runner = await RunnerFactory.create(
            runner_type="local",
            user_types=[TestUser],
            load_shape=load_shape,
            config=config
        )

        assert runner is not None
        assert runner.node == NODE_TYPE_LOCAL

    @allure.story("创建运行器")
    @allure.title("测试创建无效运行器类型")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_create_invalid_runner_type(self, base_config):
        """测试创建无效的运行器类型"""
        load_shape = TestLoadShape()

        with pytest.raises(ValueError):
            await RunnerFactory.create(
                runner_type="invalid",
                user_types=[TestUser],
                load_shape=load_shape,
                config=base_config
            )

    @allure.story("创建运行器")
    @allure.title("测试创建Master运行器")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_create_master_runner(self, redis_client):
        """测试创建Master运行器"""
        load_shape = TestLoadShape()
        config = type('Config', (), {
            'host': 'http://localhost:8080',
            'timeout': 30,
            'prometheus_port': 9090,
            'metrics_collection_interval': 5.0,
            'metrics_batch_size': 100,
            'metrics_flush_interval': 1.0,
            'metrics_buffer_size': 10000
        })()

        runner = await RunnerFactory.create(
            runner_type="master",
            user_types=[TestUser],
            load_shape=load_shape,
            config=config,
            redis_client=redis_client
        )

        assert runner is not None
        assert runner.node == NODE_TYPE_MASTER

        # 清理
        await runner.quit()

    @allure.story("创建运行器")
    @allure.title("测试创建Worker运行器")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_create_worker_runner(self, redis_client):
        """测试创建Worker运行器"""
        load_shape = TestLoadShape()
        config = type('Config', (), {
            'host': 'http://localhost:8080',
            'timeout': 30,
            'prometheus_port': 9090,
            'metrics_collection_interval': 5.0,
            'metrics_batch_size': 100,
            'metrics_flush_interval': 1.0,
            'metrics_buffer_size': 10000
        })()

        runner = await RunnerFactory.create(
            runner_type="worker",
            user_types=[TestUser],
            load_shape=load_shape,
            config=config,
            redis_client=redis_client
        )

        assert runner is not None
        assert runner.node == NODE_TYPE_WORKER

        # 清理
        await runner.quit()


@allure.feature("基础运行器异步方法")
class TestBaseRunnerAsyncMethods:
    """基础运行器异步方法的测试用例"""

    @allure.story("启动测试")
    @allure.title("测试启动测试")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_start(self, base_config):
        """测试启动测试"""
        load_shape = TestLoadShape()
        runner = BaseRunner([TestUser], load_shape, base_config)

        # 启动测试
        await runner.start()

    @allure.story("启动测试")
    @allure.title("测试启动测试无负载形状")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_start_without_load_shape(self, base_config):
        """测试没有负载形状时启动测试"""
        runner = BaseRunner([TestUser], None, base_config)

        with pytest.raises(ValueError):
            await runner.start()

    @allure.story("运行测试")
    @allure.title("测试运行直到完成")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_run_until_complete(self, base_config):
        """测试运行直到完成"""
        load_shape = TestLoadShape()
        runner = BaseRunner([TestUser], load_shape, base_config)

        # 启动测试
        await runner.start()

        # 等待一小段时间
        await asyncio.sleep(0.1)

        # 退出运行器以停止任务
        await runner.quit()

        # 运行直到完成（应该在任务完成后返回）
        await runner.run_until_complete()

    @allure.story("退出测试")
    @allure.title("测试退出运行器")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_quit(self, base_config):
        """测试退出运行器"""
        load_shape = TestLoadShape()
        runner = BaseRunner([TestUser], load_shape, base_config)

        # 启动测试
        await runner.start()

        # 等待一小段时间
        await asyncio.sleep(0.1)

        # 退出运行器
        await runner.quit()

        # 验证状态
        assert runner.state_manager.is_in_quit_state()

    @allure.story("退出测试")
    @allure.title("测试重复退出")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_quit_twice(self, base_config):
        """测试重复退出不会出错"""
        load_shape = TestLoadShape()
        runner = BaseRunner([TestUser], load_shape, base_config)

        # 启动测试
        await runner.start()

        # 等待一小段时间
        await asyncio.sleep(0.1)

        # 第一次退出
        await runner.quit()

        # 第二次退出（应该不执行任何操作）
        await runner.quit()

    @allure.story("应用负载")
    @allure.title("测试应用负载")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_apply_load(self, base_config):
        """测试应用负载配置"""
        load_shape = TestLoadShape()
        runner = BaseRunner([TestUser], load_shape, base_config)

        # 应用负载
        await runner.apply_load(user_count=5, rate=2.0)

        # 验证状态
        assert runner.state == RunnerState.RUNNING

    @allure.story("应用负载")
    @allure.title("测试应用负载无效参数")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_apply_load_invalid_params(self, base_config):
        """测试应用负载时无效参数"""
        load_shape = TestLoadShape()
        runner = BaseRunner([TestUser], load_shape, base_config)

        # 测试无效的用户数
        with pytest.raises(InvalidUserCountError):
            await runner.apply_load(user_count=0, rate=1.0)

        # 测试无效的速率
        with pytest.raises(InvalidRateError):
            await runner.apply_load(user_count=10, rate=0.0)

    @allure.story("停止测试")
    @allure.title("测试停止测试")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_stop(self, base_config):
        """测试停止测试"""
        load_shape = TestLoadShape()
        runner = BaseRunner([TestUser], load_shape, base_config)

        # 应用负载
        await runner.apply_load(user_count=5, rate=2.0)

        # 停止测试
        with pytest.raises(NotImplementedError):
            await runner.stop()

    @allure.story("CPU指标收集")
    @allure.title("测试收集CPU指标")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_collect_cpu_metrics(self, base_config):
        """测试收集CPU指标"""
        load_shape = TestLoadShape()
        runner = BaseRunner([TestUser], load_shape, base_config)

        # 启动测试
        await runner.start()

        # 等待一小段时间
        await asyncio.sleep(0.1)

        # 退出运行器
        await runner.quit()

        # 验证CPU使用率被收集
        assert isinstance(runner.cpu_usage, (int, float))


@allure.feature("高速率警告")
class TestHighRateWarning:
    """高速率警告的测试用例"""

    @allure.story("警告日志")
    @allure.title("测试高速率警告")
    @allure.severity(allure.severity_level.NORMAL)
    def test_high_rate_warning(self, base_config):
        """测试高速率警告日志 - 验证函数不抛出异常"""
        # 调用验证函数，触发高速率警告（应该正常执行，不抛出异常）
        validate_load_params(user_count=200, rate=150.0)
        # 如果函数正常执行，说明警告已记录（日志输出到控制台）


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
