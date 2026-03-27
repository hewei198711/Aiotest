# encoding: utf-8
"""
用户模块，定义用户行为和任务执行逻辑

提供用户基类和HTTP用户类，支持多种任务执行模式和灵活的等待时间设置。
"""

import asyncio
import inspect
import random
from enum import Enum, auto
from typing import Awaitable, Callable, Coroutine, Dict, List, Optional, Tuple, Union

from aiotest.clients import HTTPClient
from aiotest.logger import logger

# 等待时间类型定义：支持多种灵活的等待方式
WaitTimeType = Union[
    float,  # 固定等待时间
    Tuple[float, float],  # 随机范围 (min, max)
    Callable[[], float],  # 同步函数，返回等待时间
    Callable[[], Awaitable[float]],  # 异步函数，返回等待时间
]


class WaitTimeResolver:
    """等待时间解析器，支持多种等待时间类型"""

    @classmethod
    async def resolve_wait_time(cls, wait_time) -> float:
        """解析等待时间，返回实际等待的秒数"""

        # 1. 固定数值
        if isinstance(wait_time, (int, float)):
            return float(wait_time)

        # 2. 随机范围元组
        if isinstance(wait_time, (tuple, list)) and len(wait_time) == 2:
            return await cls._resolve_range_wait_time(wait_time)

        # 3. 同步函数
        if callable(wait_time) and not inspect.iscoroutinefunction(wait_time):
            return await cls._resolve_sync_function_wait_time(wait_time)

        # 4. 异步函数
        if inspect.iscoroutinefunction(wait_time):
            return await cls._resolve_async_function_wait_time(wait_time)

        raise ValueError(f"不支持的 wait_time 类型: {type(wait_time)}")

    @classmethod
    async def _resolve_range_wait_time(cls, wait_time_range) -> float:
        """解析范围等待时间"""
        min_val, max_val = float(wait_time_range[0]), float(wait_time_range[1])
        if min_val < 0 or max_val < 0:
            raise ValueError(f"等待时间不能为负数: min={min_val}, max={max_val}")
        if min_val > max_val:
            raise ValueError(
                f"最小等待时间不能大于最大等待时间: min={min_val}, max={max_val}")
        return random.uniform(min_val, max_val)

    @classmethod
    async def _resolve_sync_function_wait_time(cls, wait_time_func) -> float:
        """解析同步函数等待时间"""
        try:
            result = wait_time_func()
            if isinstance(result, (int, float)):
                wait_seconds = float(result)
                if wait_seconds < 0:
                    raise ValueError(f"等待时间不能为负数: {wait_seconds}")
                return wait_seconds
            if isinstance(result, (tuple, list)) and len(result) == 2:
                return await cls._resolve_range_wait_time(result)
            raise ValueError(f"wait_time 同步函数必须返回数值或范围元组，得到: {type(result)}")
        except Exception as e:
            raise ValueError(f"wait_time 同步函数执行失败: {e}") from e

    @classmethod
    async def _resolve_async_function_wait_time(cls, wait_time_func) -> float:
        """解析异步函数等待时间"""
        try:
            result = await wait_time_func()
            if isinstance(result, (int, float)):
                wait_seconds = float(result)
                if wait_seconds < 0:
                    raise ValueError(f"等待时间不能为负数: {wait_seconds}")
                return wait_seconds
            if isinstance(result, (tuple, list)) and len(result) == 2:
                return await cls._resolve_range_wait_time(result)
            raise ValueError(f"wait_time 异步函数必须返回数值或范围元组，得到: {type(result)}")
        except Exception as e:
            raise ValueError(f"wait_time 异步函数执行失败: {e}") from e

    @classmethod
    async def wait(cls, wait_time) -> None:
        """执行等待操作"""
        try:
            sleep_time = await cls.resolve_wait_time(wait_time)
            await asyncio.sleep(sleep_time)
        except Exception as e:
            logger.error("等待时间执行失败: %s, 使用默认等待时间1.0秒", e)
            await asyncio.sleep(1.0)


class ExecutionMode(Enum):
    """
    任务执行模式枚举。

    功能：
        - 定义用户任务的执行方式。
        - 支持顺序执行和并发执行两种模式。

    枚举值：
        - SEQUENTIAL: 顺序执行，任务按顺序逐个执行。
        - CONCURRENT: 并发执行，任务并行执行（受限于最大并发数）。
    """
    SEQUENTIAL = auto()  # 顺序执行
    CONCURRENT = auto()  # 并发执行


class UserMeta(type):
    """
    用户元类，用于自动收集任务函数。

    功能：
        - 自动收集以 `test_` 开头或 `_test` 结尾的协程函数作为任务。
        - 支持通过 `@weight` 装饰器设置任务权重。
        - 将收集的任务存储在 `jobs` 属性中。

    参数：
        classname (str): 类名。
        bases (tuple): 基类元组。
        class_dict (dict): 类属性字典。

    返回：
        type: 新创建的类。
    """

    def __new__(
        mcs,
        classname: str,
        bases: tuple,
        class_dict: dict,
    ) -> type:
        """自动收集 test_*/_test* 开头的协程函数作为任务，并支持权重设置"""

        jobs: List[Tuple[Callable[['User'], Coroutine[None, None, None]], int]] = []

        for key, value in class_dict.items():
            if ((key.startswith("test_") or key.endswith("_test")) and
                callable(value) and
                    inspect.iscoroutinefunction(value)):
                # 默认权重为1
                weight_val = getattr(value, 'weight', 1)
                jobs.append((value, weight_val))

        if "jobs" not in class_dict:
            class_dict["jobs"] = jobs

        return super().__new__(mcs, classname, bases, class_dict)


def weight(weight_value: int):
    """
    为任务函数设置权重。

    功能：
        - 通过装饰器为任务函数分配权重值。
        - 权重值影响任务的执行频率（权重越高，执行频率越高）。

    参数：
        weight_value (int): 权重值，必须为正整数。

    返回：
        Callable: 装饰器函数。

    异常：
        ValueError: 如果权重值不是正整数。

    示例：
        @weight(3)
        async def test_important_task(self):
            pass
    """
    if not isinstance(weight_value, int) or weight_value < 1:
        raise ValueError(
            f"权重值必须是正整数，得到: {weight_value}")

    def decorator(func):
        func.weight = weight_value
        return func
    return decorator


class User(metaclass=UserMeta):
    """
    用户基类，定义用户行为和任务执行逻辑

    特性：
    - 支持顺序执行和并发执行模式
    - 自动收集任务函数并支持权重分配
    - 内置错误处理机制
    - 支持多种灵活的等待时间设置（固定值、随机范围、自定义函数）

    属性：
    - host: 目标主机地址
    - wait_time: 任务执行间隔时间（支持固定数值、随机范围、同步/异步函数）
    - weight: 用户权重
    - max_concurrent_tasks: 最大并发任务数
    - execution_mode: 任务执行模式（SEQUENTIAL/CONCURRENT）


    wait_time 支持的类型：
    - float: 固定等待时间，如 2.0
    - tuple: 随机范围，如 (1.0, 3.0) 表示1-3秒随机
    - 同步函数: 返回数值或范围元组的函数
    - 异步函数: 返回数值或范围元组的协程函数
    """
    host: Optional[str] = None
    wait_time: WaitTimeType = 1.0
    weight: int = 1
    max_concurrent_tasks: Optional[int] = None  # 默认值将在初始化时设置为任务数
    execution_mode: ExecutionMode = ExecutionMode.SEQUENTIAL

    def __init__(
        self,
        wait_time: Optional[WaitTimeType] = None,
        weight_val: Optional[int] = None,
        max_concurrent_tasks: Optional[int] = None,
        execution_mode: Optional[ExecutionMode] = None,
    ) -> None:
        super().__init__()
        self.tasks: Optional[asyncio.Task[None]] = None
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # 初始状态为非暂停

        if wait_time is not None:
            self.wait_time = wait_time
        if weight_val is not None:
            self.weight = weight_val

        # 设置最大并发任务数
        if max_concurrent_tasks is not None:
            if max_concurrent_tasks <= 0:
                self.max_concurrent_tasks = 1
            else:
                self.max_concurrent_tasks = min(max_concurrent_tasks, 100)
        else:
            # 自动设置为任务数量，最少为1
            jobs = getattr(self, 'jobs', [])
            self.max_concurrent_tasks = max(min(len(jobs), 100), 1)

        if execution_mode is not None:
            self.execution_mode = execution_mode

        # 验证顺序执行模式下的权重约束
        self._validate_sequential_weights()

    def _validate_sequential_weights(self) -> None:
        """
        验证顺序执行模式下的权重约束

        规则：当执行模式是 ExecutionMode.SEQUENTIAL 时，所有任务的权重必须等于 1

        异常：
            ValueError: 当发现权重不等于1的任务时抛出
        """
        if self.execution_mode == ExecutionMode.SEQUENTIAL:
            jobs = getattr(self, 'jobs', [])

            if not jobs:
                return

            # 检查所有任务的权重
            invalid_jobs = []
            for job_func, job_weight in jobs:
                if job_weight != 1:
                    invalid_jobs.append((job_func.__name__, job_weight))

            # 如果有权重不等于1的任务，抛出异常
            if invalid_jobs:
                error_msg = "顺序执行模式下所有任务的权重必须等于1"
                raise ValueError(error_msg)

    async def on_start(self) -> None:
        """用户启动时调用，用于初始化资源或配置。"""

    async def on_stop(self) -> None:
        """用户停止时调用，用于清理资源或保存状态。"""

    def start_tasks(self) -> None:
        """启动用户任务。如果任务已在运行，则抛出异常。"""
        if self.tasks is not None and not self.tasks.done():
            task_state = getattr(self.tasks, '_state', 'unknown')
            raise RuntimeError(
                f"{type(self).__name__} user task is already running (state: {task_state})"
            )

        self.tasks = asyncio.create_task(self._run(), name=type(self).__name__)

    async def stop_tasks(self) -> None:
        """停止用户任务，并清理资源。如果任务未完成，则取消任务。"""

        if self.tasks is None:
            return

        if not self.tasks.done():
            self.tasks.cancel()
            try:
                await self.tasks
            except asyncio.CancelledError:
                pass

        await self.on_stop()
        self.tasks = None  # 清理引用

    async def pause_tasks(self) -> None:
        """暂停用户任务"""
        self._pause_event.clear()
        logger.info("用户任务已暂停")

    async def resume_tasks(self) -> None:
        """恢复用户任务"""
        self._pause_event.set()
        logger.info("用户任务已恢复")

    async def _wait_if_paused(self, timeout: Optional[float] = None) -> bool:
        """等待直到任务恢复或超时

        参数:
            timeout: 超时时间（秒），None表示无限期等待

        返回:
            bool: True表示成功恢复，False表示超时
        """
        try:
            if timeout:
                return await asyncio.wait_for(self._pause_event.wait(), timeout=timeout)
            else:
                await self._pause_event.wait()
                return True
        except asyncio.TimeoutError:
            logger.warning("暂停等待超时")
            return False

    async def _run(self) -> None:
        """
        用户任务主运行循环
        - 根据执行模式(顺序/并发)调用对应方法
        - 捕获并处理所有异常
        """
        try:
            await self.on_start()
            await WaitTimeResolver.wait(self.wait_time)

            if self.execution_mode == ExecutionMode.CONCURRENT:
                await self._run_concurrent()
            else:
                await self._run_sequential()

        except asyncio.CancelledError:
            await self.on_stop()
        except Exception as e:
            await self._handle_error(e)
            await self.on_stop()

    async def _run_sequential(self) -> None:
        """顺序执行所有任务，逐个完成任务。"""
        while True:
            # 检查是否暂停
            await self._wait_if_paused()
            
            jobs = getattr(self, 'jobs', [])
            if not jobs:
                break

            for job, _ in jobs:
                # 检查是否暂停
                await self._wait_if_paused()
                
                try:
                    await job(self)
                except AssertionError as e:
                    logger.warning("任务中断言失败: %s", e)
                    break  # 跳出本次循环，不执行后面的接口任务，因为后续任务依赖前面的结果
                except Exception as e:
                    await self._handle_error(e)
                    break  # 跳出本次循环，不执行后面的接口任务，因为后续任务依赖前面的结果
                # 任务后等待
                await WaitTimeResolver.wait(self.wait_time)

    async def _run_concurrent(self) -> None:
        """并发执行任务，支持权重分配和并发限制。"""

        # 获取任务列表
        jobs = getattr(self, 'jobs', [])
        if not jobs:
            return

        # 分离任务函数和权重
        jobs_list, weights_list = zip(*jobs)

        # 判断权重是否相同
        first_weight = weights_list[0]
        all_weights_same = all(w == first_weight for w in weights_list)

        # 创建信号量控制并发数
        semaphore = asyncio.Semaphore(self.max_concurrent_tasks)

        async def run_task(job: Callable[[], Coroutine]) -> None:
            """执行单个任务"""
            async with semaphore:  # 默认占用1个信号量
                # 检查是否暂停
                await self._wait_if_paused()
                
                try:
                    await job(self)
                except Exception as e:
                    await self._handle_error(e)
                finally:
                    # 检查是否暂停
                    await self._wait_if_paused()
                    
                    # 使用新的等待解析器，支持多种等待时间类型
                    await WaitTimeResolver.wait(self.wait_time)

        while True:
            # 检查是否暂停
            await self._wait_if_paused()
            
            # 根据权重选择要执行的任务
            if all_weights_same:
                # 权重相同，直接随机选择
                selected_count = min(len(jobs_list), self.max_concurrent_tasks)
                selected_jobs = random.sample(jobs_list, selected_count)
            else:
                # 权重不同，使用加权随机选择
                selected_jobs = random.choices(
                    jobs_list,
                    weights=weights_list,
                    k=self.max_concurrent_tasks
                )

            # 并发执行选中的任务
            await asyncio.gather(*[run_task(job) for job in selected_jobs])

    async def _handle_error(self, error: Exception) -> None:
        """处理任务执行中的错误。"""
        exc_type = error.__class__.__name__
        error_msg = f"{exc_type}: {str(error)}"
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            logger.warning("任务被 %s 中断", type(error).__name__)
            raise error

        logger.error("任务执行失败: %s", error_msg, exc_info=True)


class HttpUser(User):
    """
    HTTP用户类，扩展自User基类，内置HTTP客户端管理

    特性：
    - 自动管理HTTP客户端生命周期，使用上下文管理器模式
    - 支持自定义主机地址和HTTP客户端配置
    - 支持连接池配置和性能优化
    - 继承User类的任务执行功能
    - 提供更优雅的资源管理和错误处理

    属性：
    - host: HTTP服务地址
    - _client: HTTP客户端实例（延迟初始化）
    - _client_config: HTTP客户端配置参数
    - _client_initialized: 客户端是否已初始化标志
    """

    def __init__(
        self,
        host: Optional[str] = None,
        wait_time: Optional[WaitTimeType] = None,
        weight_val: Optional[int] = None,
        max_concurrent_tasks: Optional[int] = None,
        execution_mode: Optional[ExecutionMode] = None,
        client: Optional[HTTPClient] = None,
        # HTTP客户端配置参数
        default_headers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
        max_retries: int = 3,
        verify_ssl: bool = True,
    ) -> None:

        super().__init__(
            wait_time=wait_time,
            weight_val=weight_val,
            max_concurrent_tasks=max_concurrent_tasks,
            execution_mode=execution_mode,
        )

        # 设置主机地址
        if host is not None:
            self.host = host

        # 如果没有设置host且没有预配置客户端，抛出异常
        if self.host is None and client is None:
            raise ValueError("HttpUser 必须设置 host")

        # 如果传入了预配置的客户端，使用它
        if client is not None:
            self._client = client
            self._client_initialized = True
        else:
            self._client = None
            self._client_initialized = False
            # 保存客户端配置，用于延迟初始化
            self._client_config = {
                'default_headers': default_headers,
                'timeout': timeout,
                'max_retries': max_retries,
                'verify_ssl': verify_ssl,
            }

    @property
    def client(self) -> HTTPClient:
        """获取HTTP客户端实例"""
        if self._client is None or not self._client_initialized:
            raise RuntimeError("HTTP 客户端未初始化")
        return self._client

    async def _ensure_client_initialized(self) -> None:
        """确保HTTP客户端已初始化"""
        if self._client is None or not self._client_initialized:

            logger.debug("正在初始化HTTP客户端，主机: %s", self.host)

            # 创建新的客户端实例
            self._client = HTTPClient(
                base_url=self.host, **self._client_config)

            try:
                # 直接调用__aenter__方法初始化，不使用上下文管理器
                await self._client.__aenter__()
                self._client_initialized = True
                logger.debug(
                    "HTTP客户端初始化成功，主机: %s", 
                    self.host
                )
            except Exception as e:
                logger.error("初始化HTTP客户端失败: %s", e)
                self._client = None
                self._client_initialized = False
                raise

    async def on_start(self) -> None:
        """
        用户启动时的初始化逻辑

        功能：
        - 调用父类初始化
        - 自动初始化HTTP客户端
        """
        await super().on_start()

        # 自动初始化HTTP客户端
        if not self._client_initialized:
            await self._ensure_client_initialized()

    async def on_stop(self) -> None:
        """
        用户停止时的清理逻辑

        功能：
        - 优雅关闭HTTP客户端
        - 调用父类清理逻辑
        """
        if self._client is not None and self._client_initialized:
            try:
                logger.debug("正在关闭HTTP客户端，主机: %s", self.host)
                await self._client.__aexit__(None, None, None)
                logger.debug(
                    "HTTP客户端关闭成功，主机: %s", 
                    self.host
                )
            except Exception as e:
                logger.error(
                    "关闭HTTP客户端失败: %s", e,
                    exc_info=True
                )
            finally:
                self._client = None
                self._client_initialized = False

        await super().on_stop()

    async def __aenter__(self):
        """
        支持异步上下文管理器协议

        允许 HttpUser 实例直接用于 async with 语句
        """
        if not self._client_initialized:
            await self._ensure_client_initialized()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        支持异步上下文管理器协议
        """
        await self.on_stop()
