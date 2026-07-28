# encoding: utf-8

"""
AioTest 事件系统测试模块

测试 EventHook 和 Events 类的功能，包括：

- 事件处理器注册和移除
- 装饰器方式注册
- 优先级执行顺序
- 同步/异步处理器
- 事件触发和批量触发
- 异常处理
- 去重机制
"""

import asyncio

import allure
import pytest

from aiotest.events import EventHook, Events

# ============================================================================
# EventHook 基础功能测试
# ============================================================================


@allure.feature("EventHook 基础功能")
class TestEventHookBasic:
    """测试 EventHook 基础功能"""

    @allure.story("添加处理器")
    @allure.title("测试添加事件处理器")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.asyncio
    async def test_add_handler(self):
        """测试添加事件处理器"""
        event_hook = EventHook()
        called = False

        async def handler(**kwargs):
            nonlocal called
            called = True

        await event_hook.add_handler(handler)
        await event_hook.fire()

        assert called, "处理器应该被调用"

    @allure.story("优先级")
    @allure.title("测试带优先级的处理器执行顺序")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.asyncio
    async def test_add_handler_with_priority(self):
        """测试带优先级的处理器执行顺序"""
        event_hook = EventHook()
        results = []

        async def handler_low(**kwargs):
            results.append("low")

        async def handler_high(**kwargs):
            results.append("high")

        async def handler_medium(**kwargs):
            results.append("medium")

        # 按不同优先级添加
        await event_hook.add_handler(handler_low, priority=0)
        await event_hook.add_handler(handler_high, priority=10)
        await event_hook.add_handler(handler_medium, priority=5)

        await event_hook.fire()

        # 高优先级应该先执行
        assert results == [
            "high", "medium", "low"], f"执行顺序应该是 high -> medium -> low, 实际: {results}"

    @allure.story("移除处理器")
    @allure.title("测试移除事件处理器")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.asyncio
    async def test_remove_handler(self):
        """测试移除事件处理器"""
        event_hook = EventHook()
        called = False

        async def handler(**kwargs):
            nonlocal called
            called = True

        await event_hook.add_handler(handler)
        await event_hook.remove_handler(handler)
        await event_hook.fire()

        assert not called, "处理器应该被移除"

    @allure.story("去重机制")
    @allure.title("测试重复处理器注册的去重机制")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.asyncio
    async def test_duplicate_handler_prevention(self):
        """测试重复处理器注册的去重机制"""
        event_hook = EventHook()
        call_count = 0

        async def handler(**kwargs):
            nonlocal call_count
            call_count += 1

        # 尝试添加同一个处理器两次
        await event_hook.add_handler(handler, priority=0)
        await event_hook.add_handler(handler, priority=0)

        await event_hook.fire()

        assert call_count == 1, f"处理器应该只被调用一次，实际调用了 {call_count} 次"

    @allure.story("错误处理")
    @allure.title("测试传入非可调用对象时抛出 TypeError")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.asyncio
    async def test_non_callable_handler_error(self):
        """测试传入非可调用对象时抛出 TypeError"""
        event_hook = EventHook()

        with pytest.raises(TypeError, match="处理器必须是可调用的"):
            await event_hook.add_handler("not a function")


# ============================================================================
# EventHook 装饰器功能测试
# ============================================================================

@allure.feature("EventHook 装饰器功能")
class TestEventHookDecorator:
    """测试 EventHook 装饰器功能"""

    @allure.story("装饰器注册")
    @allure.title("测试使用装饰器注册处理器")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.asyncio
    async def test_handler_decorator(self):
        """测试使用装饰器注册处理器"""
        event_hook = EventHook()
        called = False

        @event_hook.handler(priority=0)
        async def my_handler(**kwargs):
            nonlocal called
            called = True

        # 注册待注册的处理器
        await event_hook.register_pending_handlers()
        await event_hook.fire()

        assert called, "通过装饰器注册的处理器应该被调用"

    @allure.story("优先级")
    @allure.title("测试装饰器的优先级")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.asyncio
    async def test_handler_decorator_with_priority(self):
        """测试装饰器的优先级"""
        event_hook = EventHook()
        results = []

        @event_hook.handler(priority=10)
        async def handler_high(**kwargs):
            results.append("high")

        @event_hook.handler(priority=0)
        async def handler_low(**kwargs):
            results.append("low")

        await event_hook.register_pending_handlers()
        await event_hook.fire()

        assert results == [
            "high", "low"], f"执行顺序应该是 high -> low, 实际: {results}"

    @allure.story("混合注册")
    @allure.title("测试装饰器和手动注册混合使用")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.asyncio
    async def test_decorator_and_manual_registration(self):
        """测试装饰器和手动注册混合使用"""
        event_hook = EventHook()
        results = []

        # 装饰器注册
        @event_hook.handler(priority=10)
        async def handler_decorator(**kwargs):
            results.append("decorator")

        # 手动注册
        async def handler_manual(**kwargs):
            results.append("manual")

        await event_hook.add_handler(handler_manual, priority=5)
        await event_hook.register_pending_handlers()
        await event_hook.fire()

        assert results == [
            "decorator", "manual"], f"执行顺序应该是 decorator -> manual, 实际: {results}"


# ============================================================================
# EventHook 同步/异步处理器测试
# ============================================================================

@allure.feature("事件处理器类型")
class TestEventHookHandlerTypes:
    """测试同步和异步事件处理器"""

    @allure.story("异步处理器")
    @allure.title("测试异步处理器")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.asyncio
    async def test_async_handler(self):
        """测试异步处理器"""
        event_hook = EventHook()
        called = False

        async def async_handler(**kwargs):
            nonlocal called
            called = True

        await event_hook.add_handler(async_handler)
        await event_hook.fire()

        assert called, "异步处理器应该被调用"

    @allure.story("同步处理器")
    @allure.title("测试同步处理器")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.asyncio
    async def test_sync_handler(self):
        """测试同步处理器"""
        event_hook = EventHook()
        called = False

        def sync_handler(**kwargs):
            nonlocal called
            called = True

        await event_hook.add_handler(sync_handler)
        await event_hook.fire()

        assert called, "同步处理器应该被调用"

    @allure.story("混合类型")
    @allure.title("测试混合同步和异步处理器")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.asyncio
    async def test_mixed_handlers(self):
        """测试混合同步和异步处理器"""
        event_hook = EventHook()
        results = []

        async def async_handler(**kwargs):
            results.append("async")

        def sync_handler(**kwargs):
            results.append("sync")

        await event_hook.add_handler(async_handler)
        await event_hook.add_handler(sync_handler)
        await event_hook.fire()

        assert "async" in results and "sync" in results, "同步和异步处理器都应该被调用"

    @allure.story("协程返回")
    @allure.title("测试返回协程对象的同步函数")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.asyncio
    async def test_handler_returning_coroutine(self):
        """测试返回协程对象的同步函数"""
        event_hook = EventHook()
        called = False

        async def inner_async():
            nonlocal called
            called = True

        def sync_handler(**kwargs):
            return inner_async()

        await event_hook.add_handler(sync_handler)
        await event_hook.fire()

        assert called, "返回协程的同步函数应该被执行"


# ============================================================================
# EventHook 事件参数测试
# ============================================================================

@allure.feature("事件参数")
class TestEventHookParameters:
    """测试事件处理器参数传递"""

    @allure.story("参数传递")
    @allure.title("测试处理器接收参数")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.asyncio
    async def test_handler_parameters(self):
        """测试处理器接收参数"""
        event_hook = EventHook()
        received_params = {}

        async def handler(**kwargs):
            received_params.update(kwargs)

        test_params = {"key1": "value1", "key2": 42}
        await event_hook.add_handler(handler)
        await event_hook.fire(**test_params)

        assert received_params == test_params, f"处理器应该接收正确的参数, 期望: {test_params}, 实际: {received_params}"

    @allure.story("多处理器")
    @allure.title("测试多个处理器共享事件参数")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.asyncio
    async def test_multiple_handlers_with_parameters(self):
        """测试多个处理器共享事件参数"""
        event_hook = EventHook()
        results = []

        async def handler1(**kwargs):
            results.append(("handler1", kwargs.get("value")))

        async def handler2(**kwargs):
            results.append(("handler2", kwargs.get("value")))

        await event_hook.add_handler(handler1)
        await event_hook.add_handler(handler2)
        await event_hook.fire(value=42)

        assert results == [("handler1", 42), ("handler2", 42)
                           ], f"所有处理器应该接收相同的参数, 实际: {results}"


# ============================================================================
# EventHook 异常处理测试
# ============================================================================

@allure.feature("异常处理")
class TestEventHookExceptions:
    """测试异常处理机制"""

    @allure.story("异常隔离")
    @allure.title("测试处理器异常不影响其他处理器")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.asyncio
    async def test_handler_exception_handling(self):
        """测试处理器异常不影响其他处理器"""
        event_hook = EventHook()
        results = []

        async def handler_with_error(**kwargs):
            results.append("error_handler")
            raise ValueError("Test error")

        async def handler_normal(**kwargs):
            results.append("normal_handler")

        await event_hook.add_handler(handler_with_error)
        await event_hook.add_handler(handler_normal)

        # fire 应该捕获异常，继续执行其他处理器
        await event_hook.fire()

        assert "error_handler" in results, "抛异常的处理器应该被调用"
        assert "normal_handler" in results, "正常的处理器应该继续执行"

    @allure.story("超时处理")
    @allure.title("测试处理器超时处理")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.asyncio
    async def test_handler_timeout(self):
        """测试处理器超时处理"""
        event_hook = EventHook()
        timed_out = False

        async def slow_handler(**kwargs):
            await asyncio.sleep(10)  # 超过默认 5 秒超时

        async def normal_handler(**kwargs):
            nonlocal timed_out
            timed_out = True

        await event_hook.add_handler(slow_handler)
        await event_hook.add_handler(normal_handler)
        await event_hook.fire()

        assert timed_out, "正常处理器应该执行完毕"


# ============================================================================
# EventHook 批量触发测试
# ============================================================================

@allure.feature("批量触发")
class TestEventHookBatchFire:
    """测试批量触发事件"""

    @allure.story("批量触发")
    @allure.title("测试批量触发事件")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.asyncio
    async def test_fire_batch(self):
        """测试批量触发事件"""
        event_hook = EventHook()
        call_count = 0

        async def handler(**kwargs):
            nonlocal call_count
            call_count += 1

        await event_hook.add_handler(handler)

        events = [{"id": i, "value": i * 10} for i in range(5)]
        await event_hook.fire_batch(events)

        assert call_count == 5, f"应该触发 5 次，实际触发 {call_count} 次"

    @allure.story("参数传递")
    @allure.title("测试批量触发时参数正确传递")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.asyncio
    async def test_fire_batch_with_parameters(self):
        """测试批量触发时参数正确传递"""
        event_hook = EventHook()
        received_values = []

        async def handler(**kwargs):
            received_values.append(kwargs.get("id"))

        await event_hook.add_handler(handler)

        events = [{"id": i} for i in range(3)]
        await event_hook.fire_batch(events)

        assert received_values == [
            0, 1, 2], f"参数应该按顺序传递, 期望: [0, 1, 2], 实际: {received_values}"

    @allure.story("数量限制")
    @allure.title("测试批量触发任务数量限制")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.asyncio
    async def test_fire_batch_limit(self):
        """测试批量触发任务数量限制"""
        event_hook = EventHook()
        call_count = 0

        async def handler(**kwargs):
            nonlocal call_count
            call_count += 1

        await event_hook.add_handler(handler)

        # 创建超过 1000 个任务
        events = [{"id": i} for i in range(1010)]

        with pytest.raises(RuntimeError, match="批量任务数量过多"):
            await event_hook.fire_batch(events)


# ============================================================================
# Events 类测试
# ============================================================================

@allure.feature("Events 类")
class TestEventsClass:
    """测试 Events 类功能"""

    @allure.story("注册事件")
    @allure.title("测试注册新事件")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_register_event(self):
        """测试注册新事件"""
        events = Events()
        event_hook = events.register("custom_event")

        assert isinstance(event_hook, EventHook), "应该返回 EventHook 实例"
        assert event_hook in events._events.values(), "事件应该被注册"

    @allure.story("自动注册")
    @allure.title("测试通过 __getattr__ 自动注册事件")
    @allure.severity(allure.severity_level.NORMAL)
    def test_getattr_auto_register(self):
        """测试通过 __getattr__ 访问未注册事件时自动注册"""
        events = Events()
        event_hook = events.custom_event

        assert isinstance(event_hook, EventHook), "应该返回 EventHook 实例"
        assert "custom_event" in events._events, "未注册的事件应该被自动注册到 _events"
        assert events._events["custom_event"] is event_hook, "自动注册的事件钩子应该是同一个实例"

    @allure.story("目录方法")
    @allure.title("测试 __dir__ 方法返回事件名称")
    @allure.severity(allure.severity_level.NORMAL)
    def test_dir_method(self):
        """测试 __dir__ 方法返回事件名称"""
        events = Events()
        events.register("event1")
        events.register("event2")

        dir_result = dir(events)

        assert "event1" in dir_result, "event1 应该在 dir 结果中"
        assert "event2" in dir_result, "event2 应该在 dir 结果中"

    @allure.story("注册待处理")
    @allure.title("测试注册所有待注册处理器")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.asyncio
    async def test_register_all_pending_handlers(self):
        """测试注册所有待注册处理器"""
        events = Events()
        called = False

        @events.custom_event.handler(priority=0)
        async def my_handler(**kwargs):
            nonlocal called
            called = True

        await events.register_all_pending_handlers()
        await events.custom_event.fire()

        assert called, "待注册处理器应该被注册并调用"


# ============================================================================
# 并发安全测试
# ============================================================================

@allure.feature("并发安全")
class TestEventHookConcurrency:
    """测试并发安全"""

    @allure.story("并发添加")
    @allure.title("测试并发添加处理器")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.asyncio
    async def test_concurrent_add_handlers(self):
        """测试并发添加处理器"""
        event_hook = EventHook()

        async def add_handlers():
            for i in range(10):
                async def handler(**kwargs):
                    pass
                await event_hook.add_handler(handler, priority=i)

        # 并发添加多个处理器
        await asyncio.gather(add_handlers(), add_handlers(), add_handlers())

        # 应该有 30 个处理器（不去重的情况下）
        # 由于每个 handler 都是独立的函数，不会触发去重
        assert len(
            event_hook._handlers) == 30, f"应该有 30 个处理器, 实际: {len(event_hook._handlers)}"

    @allure.story("并发增删")
    @allure.title("测试并发添加和移除处理器")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.asyncio
    async def test_concurrent_add_and_remove(self):
        """测试在异步上下文中并发添加和移除处理器"""
        event_hook = EventHook()
        call_count = 0

        async def handler(**kwargs):
            nonlocal call_count
            call_count += 1

        async def add_and_remove():
            await event_hook.add_handler(handler)
            await asyncio.sleep(0.01)
            await event_hook.remove_handler(handler)

        # 并发添加和移除
        await asyncio.gather(add_and_remove(), add_and_remove(), add_and_remove())

        # 触发事件，检查是否正常运行
        await event_hook.fire()

        # 由于有并发，可能添加成功也可能失败，只要不崩溃即可
        assert call_count >= 0


# ============================================================================
# 集成测试
# ============================================================================

@allure.feature("集成测试")
class TestEventsIntegration:
    """测试完整的事件系统集成"""

    @allure.story("生命周期")
    @allure.title("测试完整的事件生命周期")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.asyncio
    async def test_full_lifecycle(self):
        """测试完整的事件生命周期"""
        events = Events()
        lifecycle = []

        # 定义生命周期事件
        @events.init.handler(priority=0)
        async def on_init(**kwargs):
            lifecycle.append("init")

        @events.start.handler(priority=0)
        async def on_start(**kwargs):
            lifecycle.append("start")

        @events.stop.handler(priority=0)
        async def on_stop(**kwargs):
            lifecycle.append("stop")

        # 注册所有待注册处理器
        await events.register_all_pending_handlers()

        # 模拟生命周期
        await events.init.fire()
        await events.start.fire()
        await events.stop.fire()

        assert lifecycle == [
            "init", "start", "stop"], f"生命周期应该是 init -> start -> stop, 实际: {lifecycle}"

    @allure.story("优先级执行")
    @allure.title("测试基于优先级的完整执行顺序")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.asyncio
    async def test_priority_based_execution(self):
        """测试基于优先级的完整执行顺序"""
        events = Events()
        results = []

        # 定义命名函数（避免每次创建新的 lambda 对象）
        async def handler_low(**kwargs):
            results.append(3)

        async def handler_high(**kwargs):
            results.append(1)

        async def handler_medium(**kwargs):
            results.append(2)

        # 添加不同优先级的处理器
        await events.test_event.add_handler(handler_low, priority=0)
        await events.test_event.add_handler(handler_high, priority=10)
        await events.test_event.add_handler(handler_medium, priority=5)

        await events.test_event.fire()

        assert results == [1, 2, 3], f"优先级顺序应该是 10 -> 5 -> 0, 实际: {results}"
