# encoding: utf-8

import asyncio

import allure
import pytest

from aiotest import ExecutionMode, HttpUser, User, WaitTimeResolver, weight


@allure.feature("WaitTimeResolver")
class TestWaitTimeResolver:
    """WaitTimeResolver 类的测试用例"""

    @allure.story("解析等待时间")
    @allure.title("测试解析固定等待时间")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.parametrize("wait_time, expected", [
        (2.5, 2.5),  # 正浮点数
        (0.0, 0.0),  # 零
        (1, 1.0),  # 整数
    ])
    async def test_resolve_wait_time_float(self, wait_time, expected):
        """测试解析固定等待时间，包括正浮点数、零和整数"""
        result = await WaitTimeResolver.resolve_wait_time(wait_time)
        assert isinstance(result, float)
        assert result == expected

    @allure.story("解析等待时间")
    @allure.title("测试解析随机范围等待时间")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.parametrize("wait_time", [
        (1.0, 3.0),  # 正常范围
        (0.0, 0.0),  # 最小值等于最大值
        (2.5, 2.5),  # 浮点范围
    ])
    async def test_resolve_wait_time_tuple(self, wait_time):
        """测试解析随机范围等待时间，包括正常范围、边界情况和浮点范围"""
        result = await WaitTimeResolver.resolve_wait_time(wait_time)
        assert isinstance(result, float)
        assert wait_time[0] <= result <= wait_time[1]

    @allure.story("解析等待时间")
    @allure.title("测试解析同步函数等待时间")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.parametrize("return_value, expected_range", [
        (2.0, (2.0, 2.0)),  # 返回固定值
        ((1.0, 3.0), (1.0, 3.0)),  # 返回范围元组
    ])
    async def test_resolve_wait_time_sync_function(
            self, return_value, expected_range):
        """测试解析同步函数等待时间，包括返回固定值和范围元组的情况"""
        def sync_wait_time():
            return return_value

        result = await WaitTimeResolver.resolve_wait_time(sync_wait_time)
        assert isinstance(result, float)
        assert expected_range[0] <= result <= expected_range[1]

    @allure.story("解析等待时间")
    @allure.title("测试解析异步函数等待时间")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.parametrize("return_value, expected_range", [
        (2.0, (2.0, 2.0)),  # 返回固定值
        ((1.0, 3.0), (1.0, 3.0)),  # 返回范围元组
    ])
    async def test_resolve_wait_time_async_function(
            self, return_value, expected_range):
        """测试解析异步函数等待时间，包括返回固定值和范围元组的情况"""
        async def async_wait_time():
            return return_value

        result = await WaitTimeResolver.resolve_wait_time(async_wait_time)
        assert isinstance(result, float)
        assert expected_range[0] <= result <= expected_range[1]

    @allure.story("执行操作")
    @allure.title("测试执行等待操作")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_wait(self):
        """测试执行等待操作，验证等待时间是否符合预期"""
        start_time = asyncio.get_event_loop().time()
        # 使用适当的等待时间，确保能检测到
        await WaitTimeResolver.wait(0.1)
        end_time = asyncio.get_event_loop().time()
        # 允许一定的误差，因为系统调度可能有延迟
        assert end_time - start_time >= 0.05

    @allure.story("执行操作")
    @allure.title("测试执行等待操作时的错误处理")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_wait_with_error(self):
        def error_wait_time():
            raise ValueError("Test error")

        start_time = asyncio.get_event_loop().time()
        await WaitTimeResolver.wait(error_wait_time)
        end_time = asyncio.get_event_loop().time()
        assert end_time - start_time >= 1.0

    @allure.story("解析等待时间")
    @allure.title("测试随机范围等待时间的边界值")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_resolve_wait_time_range_equal(self):
        # 测试最小值等于最大值的情况
        wait_time = (2.0, 2.0)
        result = await WaitTimeResolver.resolve_wait_time(wait_time)
        assert isinstance(result, float)
        assert result == 2.0

    @allure.story("解析等待时间")
    @allure.title("测试函数返回范围元组的情况")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_resolve_wait_time_function_returning_range(self):
        # 测试同步函数返回范围元组
        def sync_wait_time():
            return (1.0, 3.0)

        result = await WaitTimeResolver.resolve_wait_time(sync_wait_time)
        assert isinstance(result, float)
        assert 1.0 <= result <= 3.0

        # 测试异步函数返回范围元组
        async def async_wait_time():
            return (1.0, 3.0)

        result = await WaitTimeResolver.resolve_wait_time(async_wait_time)
        assert isinstance(result, float)
        assert 1.0 <= result <= 3.0

    @allure.story("异常处理")
    @allure.title("测试同步函数返回无效类型时的异常处理")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_resolve_wait_time_sync_function_invalid_return(self):
        """测试同步函数返回无效类型时的异常处理"""
        def invalid_sync_wait_time():
            return "invalid"

        with pytest.raises(ValueError, match="同步函数必须返回数值或范围元组"):
            await WaitTimeResolver.resolve_wait_time(invalid_sync_wait_time)

    @allure.story("异常处理")
    @allure.title("测试异步函数返回无效类型时的异常处理")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_resolve_wait_time_async_function_invalid_return(self):
        """测试异步函数返回无效类型时的异常处理"""
        async def invalid_async_wait_time():
            return "invalid"

        with pytest.raises(ValueError, match="异步函数必须返回数值或范围元组"):
            await WaitTimeResolver.resolve_wait_time(invalid_async_wait_time)

    @allure.story("异常处理")
    @allure.title("测试不支持的 wait_time 类型的异常处理")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_resolve_wait_time_unsupported_type(self):
        """测试不支持的 wait_time 类型的异常处理"""
        with pytest.raises(ValueError, match="不支持的 wait_time 类型"):
            await WaitTimeResolver.resolve_wait_time([1, 2, 3])  # 列表长度为3，不是2

    @allure.story("解析等待时间")
    @allure.title("测试 Lambda 函数等待时间（无参数）")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_resolve_wait_time_lambda_no_param(self):
        """测试 Lambda 函数作为 wait_time，无参数"""
        # Lambda 函数无参数
        def wait_time(): return 2.0
        result = await WaitTimeResolver.resolve_wait_time(wait_time)
        assert isinstance(result, float)
        assert result == 2.0

    @allure.story("解析等待时间")
    @allure.title("测试 Lambda 函数等待时间（使用可变参数）")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_resolve_wait_time_lambda_with_varargs(self):
        """测试 Lambda 函数作为 wait_time，使用可变参数兼容无参数调用"""
        # Lambda 函数使用 *args 接收任意数量参数
        wait_time = lambda *args: 2.0
        result = await WaitTimeResolver.resolve_wait_time(wait_time)
        assert isinstance(result, float)
        assert result == 2.0

    @allure.story("解析等待时间")
    @allure.title("测试 Lambda 函数返回随机范围（使用可变参数）")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_resolve_wait_time_lambda_range(self):
        """测试 Lambda 函数返回随机范围，使用可变参数"""
        # Lambda 函数返回范围元组，使用 *args
        wait_time = lambda *args: (1.0, 3.0)
        result = await WaitTimeResolver.resolve_wait_time(wait_time)
        assert isinstance(result, float)
        assert 1.0 <= result <= 3.0

    @allure.story("解析等待时间")
    @allure.title("测试类方法作为异步 wait_time")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_resolve_wait_time_class_method_async(self):
        """测试类方法作为异步 wait_time 函数"""
        # 模拟用户类中的异步方法
        class MockUser:
            async def async_wait_time(self):
                return 2.5

        user = MockUser()
        wait_time = user.async_wait_time
        result = await WaitTimeResolver.resolve_wait_time(wait_time)
        assert isinstance(result, float)
        assert result == 2.5

    @allure.story("解析等待时间")
    @allure.title("测试类方法作为同步 wait_time")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_resolve_wait_time_class_method_sync(self):
        """测试类方法作为同步 wait_time 函数"""
        # 模拟用户类中的同步方法
        class MockUser:
            def sync_wait_time(self):
                return 1.5

        user = MockUser()
        wait_time = user.sync_wait_time
        result = await WaitTimeResolver.resolve_wait_time(wait_time)
        assert isinstance(result, float)
        assert result == 1.5


@allure.feature("ExecutionMode")
class TestExecutionMode:
    """ExecutionMode 枚举的测试用例"""

    @allure.story("枚举值")
    @allure.title("测试执行模式枚举值")
    @allure.severity(allure.severity_level.MINOR)
    def test_execution_mode_values(self):
        assert ExecutionMode.SEQUENTIAL.value != ExecutionMode.CONCURRENT.value
        assert hasattr(ExecutionMode, "SEQUENTIAL")
        assert hasattr(ExecutionMode, "CONCURRENT")


@allure.feature("weight decorator")
class TestWeightDecorator:
    """weight 装饰器的测试用例"""

    @allure.story("装饰器功能")
    @allure.title("测试 weight 装饰器的功能")
    @allure.severity(allure.severity_level.NORMAL)
    def test_weight_decorator(self):
        @weight(3)
        async def test_task(self):
            pass

        assert hasattr(test_task, "weight")
        assert test_task.weight == 3

    @allure.story("异常处理")
    @allure.title("测试 weight 装饰器的异常处理")
    @allure.severity(allure.severity_level.NORMAL)
    def test_weight_decorator_invalid_value(self):
        with pytest.raises(ValueError):
            @weight(0)
            async def test_task(self):
                pass

        with pytest.raises(ValueError):
            @weight(-1)
            async def test_task(self):
                pass


@allure.feature("UserMeta")
class TestUserMeta:
    """UserMeta 元类的测试用例"""

    @allure.story("任务收集")
    @allure.title("测试以 _test 结尾的任务函数收集")
    @allure.severity(allure.severity_level.NORMAL)
    def test_task_collection_with_test_suffix(self):
        class TestUserClass(User):
            async def task1_test(self):
                pass

            async def task2_test(self):
                pass

        # 验证任务是否被收集
        assert hasattr(TestUserClass, 'jobs')
        assert len(TestUserClass.jobs) == 2

        # 验证任务函数名称
        job_names = [job[0].__name__ for job in TestUserClass.jobs]
        assert 'task1_test' in job_names
        assert 'task2_test' in job_names

    @allure.story("任务收集")
    @allure.title("测试以 test_ 开头的任务函数收集")
    @allure.severity(allure.severity_level.NORMAL)
    def test_task_collection_with_test_prefix(self):
        class TestUserClass(User):
            async def test_task1(self):
                pass

            async def test_task2(self):
                pass

        # 验证任务是否被收集
        assert hasattr(TestUserClass, 'jobs')
        assert len(TestUserClass.jobs) == 2

        # 验证任务函数名称
        job_names = [job[0].__name__ for job in TestUserClass.jobs]
        assert 'test_task1' in job_names
        assert 'test_task2' in job_names

    @allure.story("任务收集")
    @allure.title("测试带有权重设置的任务函数收集")
    @allure.severity(allure.severity_level.NORMAL)
    def test_task_collection_with_weights(self):
        class TestUserClass(User):
            @weight(3)
            async def test_task1(self):
                pass

            @weight(5)
            async def test_task2(self):
                pass

        # 验证任务是否被收集
        assert hasattr(TestUserClass, 'jobs')
        assert len(TestUserClass.jobs) == 2

        # 验证任务权重是否正确
        job_weights = [job[1] for job in TestUserClass.jobs]
        assert 3 in job_weights
        assert 5 in job_weights


@allure.feature("User")
class TestUser:
    """User 基类的测试用例"""

    @allure.story("初始化")
    @allure.title("测试用户初始化")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_user_initialization(self):
        class TestUserClass(User):
            async def test_task1(self):
                pass

            async def test_task2(self):
                pass

        user = TestUserClass()
        assert user.weight == 1
        assert user.execution_mode == ExecutionMode.SEQUENTIAL
        assert user.max_concurrent_tasks == 2

    @allure.story("初始化")
    @allure.title("测试用户初始化时的自定义值")
    @allure.severity(allure.severity_level.NORMAL)
    def test_user_initialization_with_custom_values(self):
        class TestUserClass(User):
            async def test_task1(self):
                pass

        user = TestUserClass(
            wait_time=2.0,
            weight_val=5,
            max_concurrent_tasks=10,
            execution_mode=ExecutionMode.CONCURRENT
        )
        assert user.wait_time == 2.0
        assert user.weight == 5
        assert user.max_concurrent_tasks == 10
        assert user.execution_mode == ExecutionMode.CONCURRENT

    @allure.story("验证顺序执行权重")
    @allure.title("测试顺序执行模式下的权重验证")
    @allure.severity(allure.severity_level.NORMAL)
    def test_validate_sequential_weights(self):
        class TestUserClass(User):
            @weight(1)
            async def test_task1(self):
                pass

            @weight(1)
            async def test_task2(self):
                pass

        user = TestUserClass(execution_mode=ExecutionMode.SEQUENTIAL)
        assert user.execution_mode == ExecutionMode.SEQUENTIAL

    @allure.story("验证顺序执行权重")
    @allure.title("测试顺序执行模式下的权重验证失败")
    @allure.severity(allure.severity_level.NORMAL)
    def test_validate_sequential_weights_invalid(self):
        class TestUserClass(User):
            @weight(1)
            async def test_task1(self):
                pass

            @weight(2)
            async def test_task2(self):
                pass

        with pytest.raises(ValueError):
            TestUserClass(execution_mode=ExecutionMode.SEQUENTIAL)

    @allure.story("验证顺序执行权重")
    @allure.title("测试顺序执行模式下空任务列表的验证")
    @allure.severity(allure.severity_level.NORMAL)
    def test_validate_sequential_weights_empty_jobs(self):
        """测试顺序执行模式下空任务列表的验证 - 应该正常通过不抛出异常"""
        class TestUserClass(User):
            pass  # 没有任务

        # 空任务列表时应该正常通过，不抛出异常
        user = TestUserClass(execution_mode=ExecutionMode.SEQUENTIAL)
        assert user.execution_mode == ExecutionMode.SEQUENTIAL
        assert user.jobs == []

    @allure.story("任务管理")
    @allure.title("测试启动和停止任务")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_start_stop_tasks(self):
        class TestUserClass(User):
            async def test_task(self):
                await asyncio.sleep(0.1)

        user = TestUserClass()
        user.start_tasks()
        assert user.tasks is not None

        await asyncio.sleep(0.2)
        await user.stop_tasks()
        assert user.tasks is None

    @allure.story("任务管理")
    @allure.title("测试启动已在运行的任务")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_start_tasks_already_running(self):
        class TestUserClass(User):
            async def test_task(self):
                await asyncio.sleep(0.5)

        user = TestUserClass()
        user.start_tasks()

        with pytest.raises(RuntimeError):
            user.start_tasks()

        await user.stop_tasks()

    @allure.story("生命周期管理")
    @allure.title("测试 on_start 和 on_stop 方法的调用")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_on_start_on_stop(self):
        class TestUserClass(User):
            def __init__(self):
                super().__init__()
                self.on_start_called = False
                self.on_stop_called = False

            async def on_start(self):
                await super().on_start()
                self.on_start_called = True

            async def on_stop(self):
                await super().on_stop()
                self.on_stop_called = True

            async def test_task(self):
                await asyncio.sleep(0.1)

        user = TestUserClass()
        assert not user.on_start_called
        assert not user.on_stop_called

        # 启动任务，会调用 on_start
        user.start_tasks()
        await asyncio.sleep(0.2)
        assert user.on_start_called

        # 停止任务，会调用 on_stop
        await user.stop_tasks()
        assert user.on_stop_called

    @allure.story("任务执行")
    @allure.title("测试任务执行功能")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_task_execution(self):
        class TestUserClass(User):
            wait_time = 0.01  # 减少等待时间，加快测试

            def __init__(self):
                super().__init__()
                self.task_executed = False

            async def test_task(self):
                self.task_executed = True
                # 完成后退出循环
                self.jobs = []

        user = TestUserClass()
        assert not user.task_executed

        # 启动任务
        user.start_tasks()
        await asyncio.sleep(0.2)  # 等待足够时间让任务执行

        # 验证任务是否执行
        assert user.task_executed

        await user.stop_tasks()

    @allure.story("任务执行")
    @allure.title("测试顺序执行模式下任务失败的处理")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_run_sequential_with_error(self):
        class TestUserClass(User):
            wait_time = 0.01  # 减少等待时间，加快测试

            def __init__(self):
                super().__init__()
                self.first_task_executed = False
                self.second_task_executed = False

            async def test_first_task(self):
                self.first_task_executed = True
                # 清空 jobs 列表，让外部循环退出
                self.jobs = []
                raise Exception("Test error")

            async def test_second_task(self):
                self.second_task_executed = True

        user = TestUserClass()
        assert not user.first_task_executed
        assert not user.second_task_executed

        # 启动任务
        user.start_tasks()
        await asyncio.sleep(0.2)  # 等待足够时间让任务执行

        # 验证第一个任务执行了，第二个任务没有执行（因为第一个任务失败）
        assert user.first_task_executed
        assert not user.second_task_executed

        await user.stop_tasks()

    @allure.story("任务执行")
    @allure.title("测试顺序执行模式下 AssertionError 的处理")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_run_sequential_with_assertion_error(self):
        """测试顺序执行模式下 AssertionError 的处理 - 应该只记录警告，不调用 _handle_error"""
        class TestUserClass(User):
            wait_time = 0.01  # 减少等待时间，加快测试

            def __init__(self):
                super().__init__()
                self.first_task_executed = False
                self.second_task_executed = False

            async def test_first_task(self):
                self.first_task_executed = True
                # 清空 jobs 列表，让外部循环退出
                self.jobs = []
                assert False, "Test assertion error"

            async def test_second_task(self):
                self.second_task_executed = True

        user = TestUserClass()
        assert not user.first_task_executed
        assert not user.second_task_executed

        # 启动任务
        user.start_tasks()
        await asyncio.sleep(0.2)  # 等待足够时间让任务执行

        # 验证第一个任务执行了，第二个任务没有执行（因为第一个任务断言失败）
        assert user.first_task_executed
        assert not user.second_task_executed

        await user.stop_tasks()

    @allure.story("任务执行")
    @allure.title("测试并发执行模式的功能")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_run_concurrent(self):
        class TestUserClass(User):
            wait_time = 0.01  # 减少等待时间，加快测试
            execution_mode = ExecutionMode.CONCURRENT

            def __init__(self):
                super().__init__()
                self.task1_executed = False
                self.task2_executed = False

            async def test_task1(self):
                await asyncio.sleep(0.05)
                self.task1_executed = True

            async def test_task2(self):
                await asyncio.sleep(0.05)
                self.task2_executed = True

        user = TestUserClass()
        assert not user.task1_executed
        assert not user.task2_executed

        # 启动任务
        user.start_tasks()
        await asyncio.sleep(0.2)  # 等待足够时间让任务执行

        # 验证两个任务都执行了
        assert user.task1_executed
        assert user.task2_executed

        await user.stop_tasks()

    @allure.story("错误处理")
    @allure.title("测试错误处理逻辑")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_handle_error(self):
        class TestUserClass(User):
            async def test_task(self):
                raise Exception("Test error")

        user = TestUserClass()

        # 启动任务
        user.start_tasks()
        await asyncio.sleep(0.2)  # 等待足够时间让任务执行

        # 停止任务
        await user.stop_tasks()

        # 验证任务已停止
        assert user.tasks is None

    @allure.story("错误处理")
    @allure.title("测试 KeyboardInterrupt 的处理")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_handle_error_keyboard_interrupt(self):
        """测试 KeyboardInterrupt 的处理 - 应该重新抛出异常"""
        user = User()

        # 直接测试 _handle_error 方法，验证 KeyboardInterrupt 会被重新抛出
        with pytest.raises(KeyboardInterrupt):
            await user._handle_error(KeyboardInterrupt("Test keyboard interrupt"))

    @allure.story("错误处理")
    @allure.title("测试 SystemExit 的处理")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_handle_error_system_exit(self):
        """测试 SystemExit 的处理 - 应该重新抛出异常"""
        user = User()

        # 直接测试 _handle_error 方法，验证 SystemExit 会被重新抛出
        with pytest.raises(SystemExit):
            await user._handle_error(SystemExit("Test system exit"))

    @allure.story("任务执行")
    @allure.title("测试带权重的并发执行")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_concurrent_execution_with_weights(self):
        class TestUserClass(User):
            wait_time = 0.01  # 减少等待时间，加快测试
            execution_mode = ExecutionMode.CONCURRENT

            def __init__(self):
                super().__init__()
                self.task1_count = 0
                self.task2_count = 0

            @weight(3)
            async def test_task1(self):
                self.task1_count += 1
                # 执行几次后退出
                if self.task1_count + self.task2_count >= 5:
                    self.jobs = []

            @weight(1)
            async def test_task2(self):
                self.task2_count += 1
                # 执行几次后退出
                if self.task1_count + self.task2_count >= 5:
                    self.jobs = []

        user = TestUserClass()
        assert user.task1_count == 0
        assert user.task2_count == 0

        # 启动任务
        user.start_tasks()
        await asyncio.sleep(0.5)  # 等待足够时间让任务执行

        # 验证任务执行次数（task1 应该执行更多次）
        assert user.task1_count + user.task2_count >= 5
        assert user.task1_count >= user.task2_count

        await user.stop_tasks()

    @allure.story("任务执行")
    @allure.title("测试不同执行模式的切换")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_task_execution_with_different_modes(self):
        # 测试顺序执行模式
        class SequentialUser(User):
            execution_mode = ExecutionMode.SEQUENTIAL
            wait_time = 0.01

            def __init__(self):
                super().__init__()
                self.task_executed = False

            async def test_task(self):
                self.task_executed = True
                self.jobs = []

        sequential_user = SequentialUser()
        sequential_user.start_tasks()
        await asyncio.sleep(0.2)
        assert sequential_user.task_executed
        await sequential_user.stop_tasks()

        # 测试并发执行模式
        class ConcurrentUser(User):
            execution_mode = ExecutionMode.CONCURRENT
            wait_time = 0.01

            def __init__(self):
                super().__init__()
                self.task_executed = False

            async def test_task(self):
                self.task_executed = True
                self.jobs = []

        concurrent_user = ConcurrentUser()
        concurrent_user.start_tasks()
        await asyncio.sleep(0.2)
        assert concurrent_user.task_executed
        await concurrent_user.stop_tasks()

    @allure.story("错误处理")
    @allure.title("测试 _run 方法的错误处理逻辑")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_run_with_error(self):
        class TestUserClass(User):
            wait_time = 0.01

            async def test_task(self):
                # 清空 jobs 列表，让循环退出
                self.jobs = []
                raise Exception("Test error")

        user = TestUserClass()

        # 启动任务
        user.start_tasks()
        await asyncio.sleep(0.2)

        # 验证任务已执行并处理了错误
        await user.stop_tasks()
        assert user.tasks is None

    @allure.story("参数验证")
    @allure.title("测试 max_concurrent_tasks 参数的边界值")
    @allure.severity(allure.severity_level.NORMAL)
    def test_max_concurrent_tasks_boundary(self):
        class TestUserClass(User):
            async def test_task(self):
                pass

        # 测试负数
        user1 = TestUserClass(max_concurrent_tasks=-10)
        assert user1.max_concurrent_tasks == 1

        # 测试零
        user2 = TestUserClass(max_concurrent_tasks=0)
        assert user2.max_concurrent_tasks == 1

        # 测试正常值
        user3 = TestUserClass(max_concurrent_tasks=5)
        assert user3.max_concurrent_tasks == 5

        # 测试超过最大值
        user4 = TestUserClass(max_concurrent_tasks=200)
        assert user4.max_concurrent_tasks == 100

    @allure.story("任务执行")
    @allure.title("详细测试权重对任务执行频率的影响")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_task_execution_frequency(self):
        class TestUserClass(User):
            wait_time = 0.01
            execution_mode = ExecutionMode.CONCURRENT

            def __init__(self):
                super().__init__()
                self.task1_count = 0
                self.task2_count = 0
                self.task3_count = 0

            @weight(5)
            async def test_task1(self):
                self.task1_count += 1
                # 执行足够次数后退出
                if self.task1_count + self.task2_count + self.task3_count >= 15:
                    self.jobs = []

            @weight(3)
            async def test_task2(self):
                self.task2_count += 1
                # 执行足够次数后退出
                if self.task1_count + self.task2_count + self.task3_count >= 15:
                    self.jobs = []

            @weight(1)
            async def test_task3(self):
                self.task3_count += 1
                # 执行足够次数后退出
                if self.task1_count + self.task2_count + self.task3_count >= 15:
                    self.jobs = []

        user = TestUserClass()
        assert user.task1_count == 0
        assert user.task2_count == 0
        assert user.task3_count == 0

        # 启动任务
        user.start_tasks()
        await asyncio.sleep(0.5)

        # 验证任务执行次数（权重越高，执行次数应该越多）
        total_executions = user.task1_count + user.task2_count + user.task3_count
        assert total_executions >= 15
        assert user.task1_count >= user.task2_count >= user.task3_count

        await user.stop_tasks()

    @allure.story("任务执行")
    @allure.title("测试当没有任务时的行为")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_no_tasks_behavior(self):
        # 定义一个没有任务的 User 子类，设置较短的 wait_time
        class TestUserClass(User):
            wait_time = 0.01  # 减少等待时间，加快测试

        user = TestUserClass()

        # 启动任务
        user.start_tasks()
        await asyncio.sleep(0.1)  # 等待足够时间让任务执行

        # 验证任务已停止（因为没有任务）
        assert user.tasks is not None
        assert user.tasks.done()

        await user.stop_tasks()
        assert user.tasks is None

    @allure.story("初始化")
    @allure.title("测试当 max_concurrent_tasks 为 None 时的自动设置逻辑")
    @allure.severity(allure.severity_level.NORMAL)
    def test_max_concurrent_tasks_auto_setting(self):
        # 测试没有任务时的自动设置
        class TestUserClass1(User):
            pass

        user1 = TestUserClass1()
        assert user1.max_concurrent_tasks == 1  # 没有任务时默认为 1

        # 测试有多个任务时的自动设置
        class TestUserClass2(User):
            async def test_task1(self):
                pass

            async def test_task2(self):
                pass

            async def test_task3(self):
                pass

        user2 = TestUserClass2()
        assert user2.max_concurrent_tasks == 3  # 有 3 个任务时设置为 3

        # 测试任务数量超过 100 时的自动设置
        class TestUserClass3(User):
            pass

        # 手动设置 jobs 列表，模拟 150 个任务
        TestUserClass3.jobs = [(lambda self: None, 1) for _ in range(150)]
        user3 = TestUserClass3()
        assert user3.max_concurrent_tasks == 100  # 任务数量超过 100 时设置为 100

    @allure.story("暂停/恢复功能")
    @allure.title("测试暂停/恢复功能")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_pause_resume_tasks(self):
        """测试用户任务的暂停和恢复功能"""
        class TestUserClass(User):
            wait_time = 0.01  # 减少等待时间，加快测试

            def __init__(self):
                super().__init__()
                self.task_executed = False
                self.pause_detected = False

            async def test_task(self):
                # 第一次执行时暂停任务
                if not self.task_executed:
                    # 暂停任务
                    await self.pause_tasks()
                    self.pause_detected = True
                    # 等待一段时间，确保任务被暂停
                    await asyncio.sleep(0.1)
                    # 恢复任务
                    await self.resume_tasks()
                self.task_executed = True
                # 完成后退出循环
                self.jobs = []

        user = TestUserClass()
        assert not user.task_executed
        assert not user.pause_detected

        # 启动任务
        user.start_tasks()
        await asyncio.sleep(0.5)  # 等待足够时间让任务执行

        # 验证任务执行和暂停/恢复功能
        assert user.task_executed
        assert user.pause_detected

        await user.stop_tasks()

    @allure.story("暂停/恢复功能")
    @allure.title("测试_pause_event初始化状态")
    @allure.severity(allure.severity_level.NORMAL)
    def test_pause_event_initialization(self):
        """测试_pause_event的初始化状态"""
        class TestUserClass(User):
            async def test_task(self):
                pass

        user = TestUserClass()
        # 验证_pause_event初始状态为已设置（非暂停）
        assert user._pause_event.is_set()

    @allure.story("暂停/恢复功能")
    @allure.title("测试_wait_if_paused方法")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_wait_if_paused(self):
        """测试_wait_if_paused方法的功能"""
        class TestUserClass(User):
            async def test_task(self):
                pass

        user = TestUserClass()

        # 测试非暂停状态下的等待
        result = await user._wait_if_paused(timeout=0.1)
        assert result is True

        # 测试暂停状态下的等待（带超时）
        await user.pause_tasks()
        assert not user._pause_event.is_set()

        start_time = asyncio.get_event_loop().time()
        result = await user._wait_if_paused(timeout=0.2)
        end_time = asyncio.get_event_loop().time()
        assert result is False  # 应该超时
        assert end_time - start_time >= 0.2

        # 测试恢复后等待
        await user.resume_tasks()
        assert user._pause_event.is_set()

        result = await user._wait_if_paused(timeout=0.1)
        assert result is True

    @allure.story("暂停/恢复功能")
    @allure.title("测试暂停状态下的任务执行")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_task_execution_in_paused_state(self):
        """测试暂停状态下任务的执行行为"""
        class TestUserClass(User):
            wait_time = 0.01  # 减少等待时间，加快测试

            def __init__(self):
                super().__init__()
                self.task_executed = False
                self.pause_called = False

            async def test_task(self):
                # 标记任务开始执行
                self.task_executed = True
                # 暂停任务
                await self.pause_tasks()
                self.pause_called = True
                # 尝试等待（应该被阻塞）
                await asyncio.sleep(0.2)
                # 恢复任务
                await self.resume_tasks()
                # 完成后退出循环
                self.jobs = []

        user = TestUserClass()
        assert not user.task_executed
        assert not user.pause_called

        # 启动任务
        user.start_tasks()
        await asyncio.sleep(0.5)  # 等待足够时间让任务执行

        # 验证任务执行和暂停/恢复功能
        assert user.task_executed
        assert user.pause_called

        await user.stop_tasks()

    @allure.story("暂停/恢复功能")
    @allure.title("测试连续暂停/恢复操作")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_multiple_pause_resume(self):
        """测试连续的暂停和恢复操作"""
        class TestUserClass(User):
            async def test_task(self):
                pass

        user = TestUserClass()

        # 初始状态应该是已设置
        assert user._pause_event.is_set()

        # 第一次暂停
        await user.pause_tasks()
        assert not user._pause_event.is_set()

        # 第二次暂停（应该无效果）
        await user.pause_tasks()
        assert not user._pause_event.is_set()

        # 第一次恢复
        await user.resume_tasks()
        assert user._pause_event.is_set()

        # 第二次恢复（应该无效果）
        await user.resume_tasks()
        assert user._pause_event.is_set()

        # 再次暂停
        await user.pause_tasks()
        assert not user._pause_event.is_set()


@allure.feature("HttpUser")
class TestHttpUser:
    """HttpUser 类的测试用例"""

    @allure.story("初始化")
    @allure.title("测试 HTTP 用户初始化")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_http_user_initialization(self):
        user = HttpUser(host="http://localhost:8080")
        assert user.host == "http://localhost:8080"
        assert not user._client_initialized

    @allure.story("初始化")
    @allure.title("测试 HTTP 用户初始化时未设置主机地址")
    @allure.severity(allure.severity_level.NORMAL)
    def test_http_user_initialization_no_host(self):
        with pytest.raises(ValueError):
            HttpUser()

    @allure.story("客户端管理")
    @allure.title("测试 HTTP 客户端初始化")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_client_initialization(self):
        user = HttpUser(host="http://localhost:8080")
        assert not user._client_initialized

        await user._ensure_client_initialized()
        assert user._client_initialized
        assert user.client is not None

        await user.on_stop()
        assert not user._client_initialized

    @allure.story("上下文管理器")
    @allure.title("测试 HTTP 用户的上下文管理器功能")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_http_user_context_manager(self):
        async with HttpUser(host="http://localhost:8080") as user:
            assert user._client_initialized
            assert user.client is not None

        assert not user._client_initialized

    @allure.story("任务执行")
    @allure.title("测试 HTTP 用户的任务执行")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_http_user_task_execution(self):
        class TestHttpUserClass(HttpUser):
            async def test_http_task(self):
                pass

        async with TestHttpUserClass(host="http://localhost:8080") as user:
            assert user._client_initialized
            await user.test_http_task()

    @allure.story("生命周期管理")
    @allure.title("测试 HTTP 用户启动时的初始化")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_http_user_on_start(self):
        class TestHttpUserClass(HttpUser):
            def __init__(self):
                super().__init__(host="http://localhost:8080")
                self.on_start_called = False

            async def on_start(self):
                await super().on_start()
                self.on_start_called = True

        user = TestHttpUserClass()
        assert not user._client_initialized
        assert not user.on_start_called

        # 启动用户，会调用 on_start 并初始化客户端
        user.start_tasks()
        await asyncio.sleep(0.2)

        assert user.on_start_called
        assert user._client_initialized

        await user.stop_tasks()

    @allure.story("生命周期管理")
    @allure.title("测试 HTTP 用户停止时的清理")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_http_user_on_stop(self):
        class TestHttpUserClass(HttpUser):
            def __init__(self):
                super().__init__(host="http://localhost:8080")
                self.on_stop_called = False

            async def on_stop(self):
                await super().on_stop()
                self.on_stop_called = True

        user = TestHttpUserClass()

        # 初始化客户端
        await user._ensure_client_initialized()
        assert user._client_initialized
        assert not user.on_stop_called

        # 停止用户，会调用 on_stop 并清理客户端
        await user.on_stop()

        assert user.on_stop_called
        assert not user._client_initialized
        assert user._client is None

    @allure.story("生命周期管理")
    @allure.title("测试 HTTP 用户停止时关闭客户端异常的处理")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_http_user_on_stop_with_close_error(self):
        """测试 HttpUser.on_stop 中关闭客户端时发生异常的处理"""
        class MockClient:
            def __init__(self):
                self.closed = False

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                self.closed = True
                raise Exception("Close error")  # 模拟关闭时发生异常

        class TestHttpUserClass(HttpUser):
            def __init__(self):
                super().__init__(host="http://localhost:8080")
                self.on_stop_called = False

            async def on_stop(self):
                await super().on_stop()
                self.on_stop_called = True

        user = TestHttpUserClass()
        # 使用模拟客户端替换真实客户端
        user._client = MockClient()
        user._client_initialized = True

        # 停止用户，应该会处理关闭客户端时的异常
        await user.on_stop()

        # 验证即使关闭客户端时发生异常，on_stop 仍然完成
        assert user.on_stop_called
        assert not user._client_initialized
        assert user._client is None

    @allure.story("客户端管理")
    @allure.title("测试客户端初始化逻辑")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_ensure_client_initialized(self):
        user = HttpUser(host="http://localhost:8080")
        assert not user._client_initialized

        # 初始化客户端
        await user._ensure_client_initialized()
        assert user._client_initialized
        assert user.client is not None

        # 再次调用应该不会重新初始化
        await user._ensure_client_initialized()
        assert user._client_initialized

        await user.on_stop()
        assert not user._client_initialized

    @allure.story("客户端配置")
    @allure.title("测试不同的客户端配置参数")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_http_user_with_custom_client_config(self):
        # 测试自定义客户端配置
        user = HttpUser(
            host="http://localhost:8080",
            default_headers={"Authorization": "Bearer token"},
            timeout=60,
            max_retries=5,
            verify_ssl=False
        )

        # 初始化客户端
        await user._ensure_client_initialized()
        assert user._client_initialized

        # 验证客户端配置（这里我们只能验证客户端存在，因为配置是内部的）
        assert user.client is not None

        await user.on_stop()
        assert not user._client_initialized

    @allure.story("客户端配置")
    @allure.title("测试使用预配置客户端的情况")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_http_user_with_preconfigured_client(
            self, preconfigured_http_client):
        """测试使用预配置客户端创建 HttpUser 的情况"""
        # 使用预配置客户端创建 HttpUser
        user = HttpUser(client=preconfigured_http_client)
        assert user._client_initialized
        assert user.client is preconfigured_http_client

        # 验证客户端正常工作
        await user.on_start()
        assert user._client_initialized

        await user.on_stop()
        # 注意：使用预配置客户端时，on_stop 会关闭客户端
        assert not user._client_initialized

    @allure.story("初始化")
    @allure.title("测试当 host 为 None 但提供了预配置客户端时的行为")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_http_user_with_none_host_and_preconfigured_client(
            self, preconfigured_http_client):
        """测试当 host 为 None 但提供了预配置客户端时的行为"""
        # 使用预配置客户端创建 HttpUser，host 为 None
        user = HttpUser(host=None, client=preconfigured_http_client)
        assert user.host is None
        assert user._client_initialized
        assert user.client is preconfigured_http_client

        # 验证客户端正常工作
        await user.on_start()
        assert user._client_initialized

        await user.on_stop()
        # 注意：使用预配置客户端时，on_stop 会关闭客户端
        assert not user._client_initialized

    @allure.story("错误处理")
    @allure.title("测试客户端操作过程中的异常处理")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_http_client_error_handling(self, http_user):
        """测试客户端操作过程中的异常处理，确保异常不会导致测试失败"""
        # 尝试访问一个不存在的端点，应该会抛出异常
        with pytest.raises(Exception):
            await http_user.client.get("/nonexistent")

        # 验证客户端仍然可用
        assert http_user._client_initialized

    @allure.story("错误处理")
    @allure.title("测试客户端操作时的网络异常处理")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_http_client_network_error_handling(self):
        """测试客户端操作时的网络异常处理"""
        # 创建一个 HttpUser，使用一个无效的 host，这样实际请求时会失败
        user = HttpUser(host="http://invalid-host-12345.com")
        assert not user._client_initialized

        # 初始化客户端（这一步不会失败，因为只是创建会话）
        await user._ensure_client_initialized()
        assert user._client_initialized

        # 尝试发送请求，应该会抛出网络异常
        with pytest.raises(Exception):
            await user.client.get("/")

        # 验证客户端仍然初始化状态（即使请求失败，客户端仍然可用）
        assert user._client_initialized


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
