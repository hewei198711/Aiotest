# encoding: utf-8

import asyncio
import sys
import traceback
from typing import Any, Callable, Dict, List, Tuple

from aiotest.logger import logger

# ============================================================================
# 核心事件系统类
# ============================================================================


class EventHook:
    """
    异步事件钩子，支持优先级和线程安全。

    功能：
        - 基于优先级的事件处理器执行。
        - 线程安全的处理器添加/移除操作。
        - 支持批量触发事件。
        - 支持装饰器式注册。

    使用场景：
        - 动态注册事件处理器。
        - 并发执行事件处理器。
        - 处理高优先级任务。
    """

    def __init__(self):
        self._handlers: List[Tuple[int, Callable[..., Any]]] = []
        self._lock = asyncio.Lock()
        # 待注册的装饰器处理器
        self._pending_handlers: List[Tuple[Callable[..., Any], int]] = []

    def handler(self, priority: int = 0):
        """
        事件处理器装饰器 - 用于声明式注册事件处理器

        参数：
            priority (int): 优先级，数值越大优先级越高，默认为 0

        使用示例：
            from aiotest import test_start

            @test_start.handler(priority=0)
            async def my_test_start_handler(**kwargs):
                print("测试开始")

        返回：
            装饰器函数
        """
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self._pending_handlers.append((func, priority))
            return func
        return decorator

    async def add_handler(
        self,
        handler: Callable[..., Any],
        priority: int = 0
    ) -> None:
        """
        添加事件处理器。

        参数：
            handler (Callable[..., Any]): 事件处理器函数。
            priority (int, 可选): 处理器的优先级，数值越高越先执行。默认为 0。
        """
        if not callable(handler):
            raise TypeError("处理器必须是可调用的")
        handler_name = getattr(handler, "__name__", repr(handler))
        async with self._lock:
            # 使用对象标识进行去重，避免同名方法被误判
            for _, existing_handler in self._handlers:
                if existing_handler is handler:
                    logger.warning("处理器 %s 已存在", handler_name)
                    return  # 如果处理器对象已存在，直接返回不添加
            # 使用优先级作为排序键，避免直接比较函数对象
            self._handlers.append((-priority, handler))
            self._handlers.sort(key=lambda x: x[0])
            logger.info(
                "已添加处理器 %s，优先级: %d", handler_name, priority)

    async def register_pending_handlers(self):
        """
        注册所有通过装饰器定义的待注册处理器

        通常在 init_events 触发时调用此方法，
        将所有使用 @event_hook.handler() 装饰器定义的处理器注册到此事件钩子中。
        """
        handler_count = len(self._pending_handlers)
        for handler, priority in self._pending_handlers:
            await self.add_handler(handler, priority=priority)
        self._pending_handlers.clear()
        return handler_count

    async def remove_handler(self, handler: Callable[..., Any]) -> None:
        """
        移除事件处理器。

        参数：
            handler (Callable[..., Any]): 要移除的事件处理器函数。
        """
        async with self._lock:
            self._handlers = [h for h in self._handlers if h[1] != handler]

    async def fire(self, **kwargs: Any) -> None:
        """
        触发事件。

        参数：
            **kwargs (Any): 传递给事件处理器的参数。
        """
        handlers = [h[1] for h in self._handlers]  # 提取排序后的处理器
        tasks = [self._safe_execute(h, **kwargs) for h in handlers]  # 创建任务
        await asyncio.gather(*tasks, return_exceptions=True)  # 并发执行

    async def fire_batch(self, events: List[Dict[str, Any]]) -> None:
        """
        批量触发事件。

        参数：
            events (List[Dict[str, Any]]): 事件字典列表。

        异常：
            RuntimeError: 如果任务数量超过限制（1000）。
        """
        if len(events) * len(self._handlers) > 1000:
            raise RuntimeError("批量任务数量过多")
        handlers = [h[1] for h in self._handlers]  # 提取排序后的处理器
        # 创建任务：生成器
        tasks = (
            self._safe_execute(handler, **event)
            for event in events
            for handler in handlers
        )
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _safe_execute(
        self,
        handler: Callable[..., Any],
        **kwargs: Any
    ) -> None:
        """
        安全执行事件处理器，支持超时和错误处理。

        参数：
            handler (Callable[..., Any]): 事件处理器函数。
            **kwargs (Any): 传递给处理器的参数。
        """
        try:
            # 检查处理器类型
            if asyncio.iscoroutinefunction(handler):
                # 协程函数，直接调用并等待
                await asyncio.wait_for(handler(**kwargs), timeout=5.0)
            else:
                # 调用处理器
                result = handler(**kwargs)
                # 如果返回协程对象，等待它
                if asyncio.iscoroutine(result):
                    await asyncio.wait_for(result, timeout=5.0)
                else:
                    # 同步函数，在执行器中运行
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, lambda: handler(**kwargs))
        except asyncio.TimeoutError:
            logger.warning(
                "处理器超时: %s",
                getattr(
                    handler,
                    '__name__',
                    repr(handler)))
        except Exception as e:
            logger.error(
                "事件处理器 %s 发生错误:\n错误: %s\n堆栈: %s",
                getattr(handler, '__name__', repr(handler)),
                e,
                ''.join(traceback.format_tb(sys.exc_info()[2]))
            )


class Events:
    """
    集中式事件系统管理。

    功能：
    - 动态事件注册。
    - 自动创建事件钩子。
    - 预定义测试生命周期的核心事件。
    - 自动注册装饰器定义的处理器。
    """

    def __init__(self):
        self._events: Dict[str, EventHook] = {}

    def register(self, name: str) -> EventHook:
        """
        注册新事件类型。

        参数：
            name (str): 事件类型名称。

        返回：
            EventHook: 注册事件的事件钩子实例。
        """
        if name not in self._events:
            self._events[name] = EventHook()
        return self._events[name]

    async def register_all_pending_handlers(self):
        """
        注册所有事件钩子的待注册处理器

        通常在 init_events 触发时调用此方法，
        将所有使用装饰器定义的处理器注册到对应的事件钩子中。
        """
        total_count = 0
        for event_hook in self._events.values():
            count = await event_hook.register_pending_handlers()
            total_count += count
        logger.info("已注册 %d 个事件处理器（通过装饰器）", total_count)

    def __getattr__(self, name: str) -> EventHook:
        """
        获取事件钩子，如果不存在则自动注册。

        参数：
            name (str): 事件钩子名称。

        返回：
            EventHook: 事件钩子实例。
        """
        if name not in self._events:
            self.register(name)
        return self._events[name]

    def __dir__(self):
        return list(self._events.keys())


# 全局事件系统实例 - 用于动态事件注册
events = Events()

# 预定义核心事件 - 直接导出使用
# 测试生命周期事件
init_events = events.register("init_events")  # 初始化事件
test_start = events.register("test_start")  # 测试开始事件
test_stop = events.register("test_stop")    # 测试停止事件
test_quit = events.register("test_quit")    # 测试退出事件
startup_completed = events.register("startup_completed")  # 启动完成事件

# 性能指标事件
# 请求指标事件(local节点：性能数据报告给prometheus，worker节点: 性能数据推送给redis)
request_metrics = events.register("request_metrics")
worker_request_metrics = events.register(
    "worker_request_metrics")  # master节点接收worker请求指标事件

# ============================================================================
# 导出所有事件以支持直接导入
# ============================================================================

__all__ = [
    # 全局事件系统
    'events',
    'EventHook',

    # 测试生命周期事件
    'init_events',
    'test_start',
    'test_stop',
    'test_quit',
    'startup_completed',

    # 性能指标事件
    'request_metrics',
    'worker_request_metrics',
]
