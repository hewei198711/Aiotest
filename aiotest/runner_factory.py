# encoding: utf-8

import asyncio
import socket
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type

import psutil
from redis.asyncio import Redis

from aiotest.events import (startup_completed, test_quit, test_start,
                            worker_request_metrics)
from aiotest.exception import InvalidRateError, InvalidUserCountError
from aiotest.load_shape_manager import LoadShapeManager
from aiotest.logger import logger
from aiotest.metrics import RequestMetrics
from aiotest.state_manager import RunnerState, StateManager
from aiotest.task_manager import TaskManager
from aiotest.user_manager import UserManager

# ============================================================================
# 运行器节点类型常量
# ============================================================================
NODE_TYPE_LOCAL = "local"
NODE_TYPE_MASTER = "master"
NODE_TYPE_WORKER = "worker"
if TYPE_CHECKING:
    from aiotest.users import User


def validate_load_params(user_count: int, rate: float) -> None:
    """
    验证负载测试参数

    参数:
        user_count: 用户数量，必须为正整数
        rate: 速率，必须大于0且不超过用户数量

    异常:
        InvalidUserCountError: 当user_count不是正整数时抛出
        InvalidRateError: 当rate不在有效范围内时抛出
    """
    if not isinstance(user_count, int) or user_count <= 0:
        raise InvalidUserCountError(
            f"用户数量必须是正整数，当前值: {user_count}")

    if rate <= 0 or rate > user_count:
        raise InvalidRateError(
            f"速率必须大于 0 且不超过 {user_count}，当前值: {rate}")

    # 速率过高警告
    if rate > 100:
        logger.warning(
            "高生成率（>100 用户/秒）可能导致性能问题")


async def register_event_handlers(runner) -> None:
    """根据运行器节点类型注册相应的事件处理器（重复注册由事件系统自身去重）。"""
    if runner.node != NODE_TYPE_WORKER:
        await startup_completed.add_handler(on_startup_completed)
    if runner.node == NODE_TYPE_MASTER:
        await worker_request_metrics.add_handler(on_worker_request_metrics)
    logger.debug("已为 %s 节点注册事件处理器", runner.node)


class RunnerFactory:
    """运行器工厂，负责创建和初始化不同类型的运行器"""

    @staticmethod
    async def create(
        runner_type: str,
        user_types: List[Type['User']],
        load_shape: Any,
        config: Dict[str, Any],
        redis_client: Optional[Redis] = None
    ) -> Any:
        """
        创建指定类型的运行器实例

        参数：
            runner_type: 运行器类型 ("local", "master", "worker")
            user_types: 用户类列表
            load_shape: 负载形状类
            config: 配置参数
            redis_client: Redis客户端（分布式模式需要）

        返回：
            初始化完成的运行器实例

        异常：
            ValueError: 当运行器类型无效时抛出
        """
        runner_type = runner_type.lower()

        # 延迟导入以避免循环依赖
        if runner_type == "local":
            from aiotest.runners import LocalRunner
            runner = LocalRunner(user_types, load_shape, config)
        elif runner_type == "master":
            from aiotest.runners import MasterRunner
            runner = MasterRunner(user_types, load_shape, config, redis_client)
        elif runner_type == "worker":
            from aiotest.runners import WorkerRunner
            runner = WorkerRunner(user_types, load_shape, config, redis_client)
        else:
            raise ValueError(
                f"未知的运行器类型: {runner_type}。可用类型: local, master, worker")

        # 初始化运行器
        await runner.initialize()

        # 注册事件处理器（去重由事件系统自身保证）
        await register_event_handlers(runner)

        logger.info("已创建并初始化 %s 运行器", runner_type)
        return runner


class BaseRunner:
    """基础运行器，提供组合式架构的核心组件"""

    def __init__(self, user_types: List[Type['User']],
                 load_shape: Any, config: Dict[str, Any]):
        """
        初始化基础运行器

        参数：
            user_types: 用户类列表
            load_shape: 负载形状控制类
            config: 配置选项
        """
        # 基础属性
        self.user_types = user_types  # 保存用户类型列表
        self.load_shape = load_shape
        self.config = config
        self.node = None  # 节点类型，由子类设置
        self.cpu_usage = 0
        self.machine_id = None  # 机器标识符，用于区分不同机器上的Worker

        # 延迟初始化组件（避免循环导入）
        self._user_manager = None
        self._state_manager = None
        self._task_manager = None
        self._load_shape_manager = None

    @property
    def user_manager(self):
        if self._user_manager is None:
            self._user_manager = UserManager(self.user_types, self.config)
        return self._user_manager

    @property
    def state_manager(self):
        if self._state_manager is None:
            self._state_manager = StateManager()
        return self._state_manager

    @property
    def task_manager(self):
        if self._task_manager is None:
            self._task_manager = TaskManager()
        return self._task_manager

    @property
    def load_shape_manager(self):
        """获取负载形状管理器"""
        if self._load_shape_manager is None and self.load_shape:
            self._load_shape_manager = LoadShapeManager(
                self.load_shape, self.apply_load)
        return self._load_shape_manager

    async def initialize(self):
        """初始化运行器（子类覆写时需调用 super()）"""
        # 获取机器标识符（使用主机名）
        self.machine_id = socket.gethostname()

    async def _init_metrics(self, redis_client=None, node_id=None, coordinator=None):
        """
        初始化指标收集器（通用方法，供子类调用）

        参数：
            redis_client: Redis 客户端（分布式模式需要）
            node_id: 节点 ID
            coordinator: 分布式协调器
        """
        from aiotest.runners import init_metrics_collector

        self.metrics_collection_interval = self.config.metrics_collection_interval

        self.metrics_collector = await init_metrics_collector(
            self.node,
            redis_client,
            node_id,
            coordinator,
            batch_size=self.config.metrics_batch_size,
            flush_interval=self.config.metrics_flush_interval,
            buffer_size=self.config.metrics_buffer_size
        )

    async def start(self) -> None:
        """启动测试：从load_shape获取用户数和速率并执行测试"""
        if not self.load_shape:
            raise ValueError(
                "负载形状是必需的但未初始化。请检查运行器创建。")

        # 使用负载形状管理器启动测试
        await self.load_shape_manager.start()

    async def run_until_complete(self) -> None:
        """运行测试直到完成"""
        if self.load_shape_manager and self.load_shape_manager.task:
            await self.load_shape_manager.task

    async def quit(self):
        """退出运行器"""
        if self.state_manager.is_in_quit_state():
            return

        # 停止负载形状管理器
        if self._load_shape_manager:
            await self._load_shape_manager.stop()

        # 退出真相是 is_quit 标志：set_quit_state() 置位后
        # transition_state 会因 is_quit 早退而失效，无需再转换状态
        self.state_manager.set_quit_state()

        try:
            # 停止所有用户
            await self.user_manager.stop_all_users()

            # 取消所有后台任务
            await self.task_manager.cancel_all_tasks()

            # 停止指标收集器并清理 Prometheus 服务
            # （部分子类无这些属性，用 getattr 跳过）
            metrics_collector = getattr(self, 'metrics_collector', None)
            if metrics_collector:
                await metrics_collector.stop()

            prometheus_runner = getattr(self, 'prometheus_runner', None)
            if prometheus_runner:
                await prometheus_runner.cleanup()
                self.prometheus_runner = None
                self.prometheus_server_started = False

            # 触发测试退出事件（quit 入口有 is_quit 早退保护，不会重复触发）
            await test_quit.fire(runner=self)

            logger.info("%s 已成功退出", self.__class__.__name__)
        except Exception as e:
            logger.error("退出过程中出错: %s", str(e))
            raise

    async def pause(self) -> None:
        """暂停测试"""
        if not self.state_manager.can_pause():
            current_state = self.state_manager.get_current_state()
            logger.warning("无法从 %s 状态暂停，忽略暂停请求", current_state)
            return

        await self.state_manager.transition_state(RunnerState.PAUSED)
        # 暂停负载形状的计时
        if self.load_shape:
            self.load_shape.pause()
        # 暂停用户活动
        await self.user_manager.pause_all_users()
        logger.info("测试已暂停")

    async def resume(self) -> None:
        """恢复测试"""
        if not self.state_manager.can_resume():
            current_state = self.state_manager.get_current_state()
            logger.warning("无法从 %s 状态恢复，忽略恢复请求", current_state)
            return

        await self.state_manager.transition_state(RunnerState.RUNNING)
        # 恢复负载形状的计时
        if self.load_shape:
            self.load_shape.resume()
        # 恢复用户活动
        await self.user_manager.resume_all_users()
        logger.info("测试已恢复")

    async def apply_load(self, user_count: int, rate: float) -> None:
        """应用负载配置：直接管理用户并更新状态"""
        validate_load_params(user_count, rate)

        # 初始状态处理
        if self.state_manager.can_start():
            await test_start.fire(runner=self)
            await self.state_manager.transition_state(RunnerState.STARTING)

        # 直接管理用户
        current_count = self.active_user_count
        if user_count > current_count:
            await self.user_manager.manage_users(user_count - current_count, rate, "start")
        elif user_count < current_count:
            await self.user_manager.manage_users(current_count - user_count, rate, "stop")
            self.user_manager.cleanup_inactive_users()

        # 首次启动设置运行状态
        if self.state_manager.get_current_state() == RunnerState.STARTING:
            await self.state_manager.transition_state(RunnerState.RUNNING)
            # 只有非Worker节点才触发全局启动完成事件
            if self.node != NODE_TYPE_WORKER:
                await startup_completed.fire(runner=self, node_type=self.node)

    async def stop(self) -> None:
        """停止负载测试（由子类重写）"""
        raise NotImplementedError("Subclass must implement stop method")

    @property
    def active_user_count(self) -> int:
        """获取当前活跃用户数量"""
        return self.user_manager.active_user_count

    @property
    def state(self):
        """获取当前状态"""
        return self.state_manager.get_current_state()

    async def _collect_cpu_metrics(self):
        """
        收集CPU使用率的通用方法

        适用于LocalRunner和WorkerRunner节点
        定期采集CPU使用率并更新self.cpu_usage属性
        """
        while not self.state_manager.is_in_quit_state():
            try:
                # 使用非阻塞模式（interval=None），返回自上次调用以来的CPU使用率。
                # interval=1 会同步阻塞事件循环1秒，严重干扰压测请求与延迟测量。
                self.cpu_usage = psutil.cpu_percent(interval=None)

                # 性能预警
                if self.cpu_usage > 90:
                    logger.warning(
                        "%s CPU 使用率超过 90%%！(当前: %.1f%%)",
                        self.__class__.__name__, self.cpu_usage)
            except Exception as e:
                logger.error(
                    "%s 收集 CPU 指标失败: %s",
                    self.__class__.__name__, str(e))
            finally:
                await asyncio.sleep(5)


# ============================================================================
# 事件处理器方法 - 集中管理所有运行器相关的事件处理逻辑
# ============================================================================

async def on_startup_completed(node_type: str, **kwargs: Any) -> None:
    """启动完成事件处理：节点进入 RUNNING 并记录启动汇总"""
    runner = kwargs["runner"]
    await runner.state_manager.transition_state(RunnerState.RUNNING)

    if node_type == NODE_TYPE_MASTER:
        tracker = runner._startup_completion_tracker
        logger.info(
            "Master 启动完成: %d 个用户，共 %d/%d 个 Worker",
            tracker.get("startup_data", {}).get("user_count", 0),
            len(tracker.get("completed_workers", set())),
            tracker.get("expected_workers", 0))
    elif node_type == NODE_TYPE_LOCAL:
        logger.info("启动完成事件: 已启动 %d 个用户", runner.active_user_count)
    # Worker 不注册本处理器，不会走到这里


async def on_worker_request_metrics(node_type: str, **kwargs: Any) -> None:
    """处理接收到的工作节点请求指标数据事件"""
    # 只在Master节点处理Worker请求指标
    if node_type != NODE_TYPE_MASTER:
        return

    data = kwargs.get("data")
    if not data:
        return

    metrics = RequestMetrics(
        request_id=data.get("request_id", ""),
        method=data.get("method", "unknown"),
        endpoint=data.get("endpoint", "unknown"),
        status_code=data.get("status_code", 0),
        duration=data.get("duration", 0),
        response_size=data.get("response_size", 0),
        error=data.get("error", None)
    )
    await kwargs["runner"].metrics_collector.process_request_metrics(metrics=metrics)
