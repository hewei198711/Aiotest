# encoding: utf-8

import asyncio
import time
from typing import Dict, List
from uuid import uuid4

from aiohttp import web
from prometheus_client import generate_latest

from aiotest.distributed_coordinator import HEARTBEAT_INTERVAL, DistributedCoordinator
from aiotest.events import (
    startup_completed,
    test_start,
    test_stop,
    worker_request_metrics,
)
from aiotest.exception import RunnerError
from aiotest.load_shape_manager import LoadShapeManager
from aiotest.logger import logger
from aiotest.metrics import REGISTRY, init_unified_collector
from aiotest.runner_factory import (
    NODE_TYPE_LOCAL,
    NODE_TYPE_MASTER,
    NODE_TYPE_WORKER,
    BaseRunner,
)
from aiotest.state_manager import RunnerState

# =============================================================================
# 辅助函数
# =============================================================================


def create_prometheus_app(runner=None):
    """创建Prometheus指标HTTP应用"""
    app = web.Application()

    async def metrics_handler(_):
        """处理/metrics端点"""
        try:
            output_bytes = generate_latest(REGISTRY)
            output_str = output_bytes.decode('utf-8', errors='replace')
            return web.Response(
                text=output_str, content_type='text/plain', charset='utf-8')
        except Exception as e:
            logger.error("指标处理程序错误: %s", str(e))
            import traceback
            logger.error(traceback.format_exc())
            return web.Response(body=b'Internal Server Error', status=500)

    async def control_handler(request):
        """处理控制请求"""
        action = request.match_info['action']
        if not runner:
            return web.Response(body=b'Runner not available', status=500)

        try:
            if action == 'pause':
                await runner.pause()
                return web.Response(body=b'Paused', status=200)
            elif action == 'resume':
                await runner.resume()
                return web.Response(body=b'Running', status=200)
            elif action == 'quit':
                await runner.quit()
                return web.Response(body=b'Quitting', status=200)
            else:
                return web.Response(body=b'Invalid action', status=400)
        except Exception as e:
            logger.error("控制请求处理错误: %s", str(e))
            return web.Response(body=b'Internal Server Error', status=500)

    async def index_handler(_):
        """处理根路径，返回Web控制界面"""
        # 读取静态HTML文件
        import os
        static_dir = os.path.join(os.path.dirname(__file__), 'static')
        html_path = os.path.join(static_dir, 'index.html')
        
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                html = f.read()
            return web.Response(text=html, content_type='text/html')
        except Exception as e:
            logger.error("读取HTML文件失败: %s", str(e))
            return web.Response(body=b'Error loading control page', status=500)

    app.router.add_get('/metrics', metrics_handler)
    app.router.add_get('/control/{action}', control_handler)
    app.router.add_get('/', index_handler)
    return app


async def init_metrics_collector(
        node, redis_client, node_id, coordinator, batch_size=100, flush_interval=1.0, buffer_size=10000):
    """
    初始化指标收集器的通用方法

    参数：
        node: 节点类型
        redis_client: Redis客户端
        node_id: 节点ID
        coordinator: 分布式协调器
        batch_size: 批量大小
        flush_interval: 刷新间隔
        buffer_size: 缓冲区大小
    """
    metrics_collector = init_unified_collector(
        node,
        redis_client,
        node_id,
        coordinator,
        batch_size=batch_size,
        flush_interval=flush_interval,
        buffer_size=buffer_size
    )
    # 启动指标收集器（注册事件处理器）
    await metrics_collector.start()
    return metrics_collector


async def start_prometheus_service(config, runner=None):
    """
    启动Prometheus HTTP服务的通用方法

    参数：
        config: 配置对象
        runner: 运行器实例，用于控制测试
    """
    prometheus_runner = web.AppRunner(create_prometheus_app(runner))
    await prometheus_runner.setup()
    site = web.TCPSite(prometheus_runner, '0.0.0.0', config.prometheus_port)
    await site.start()
    logger.info(
        "Prometheus服务已启动，监听端口: %s", config.prometheus_port)
    return prometheus_runner, True


# =============================================================================
# 数据类
# =============================================================================

class WorkerNode:
    """
    工作节点信息数据类（纯数据结构）

    设计原则：
    - 不包含心跳逻辑，由 DistributedCoordinator 统一管理
    - 只缓存从 Redis 获取的最新状态
    - 作为 Master 端的节点状态镜像

    清理机制：
    - 失联Worker通过 get_healthy_workers() 按需清理
    - 提供两阶段清理：先标记MISSING，60秒宽限期后删除
    - 避免持续轮询开销，提高资源利用效率
    """

    def __init__(self, node_id: str):
        self.node_id = node_id  # 节点唯一标识符
        self.status = RunnerState.READY  # 节点状态
        self.cpu_usage = 0.0  # CPU使用率
        self.active_users = 0  # 活跃用户数
        self.last_update = 0.0  # 最后更新时间（本地缓存）
        self.machine_id = None  # 机器标识符，用于区分不同机器上的Worker

    def update_from_heartbeat(self, heartbeat_data: dict) -> None:
        """
        从心跳数据更新节点状态

        参数：
            heartbeat_data: 从 Redis 获取的心跳数据
        """
        self.cpu_usage = float(heartbeat_data.get("cpu_percent", 0.0))
        self.active_users = int(heartbeat_data.get("active_users", 0))
        self.machine_id = heartbeat_data.get("machine_id")
        self.last_update = time.time()

        # 更新状态（如果心跳数据包含状态信息）
        status_str = heartbeat_data.get("status")
        if status_str:
            try:
                self.status = RunnerState(status_str)
            except ValueError:
                pass  # 保持原状态

    def is_stale(self, timeout_seconds: float = 10.0) -> bool:
        """
        检查节点是否处于过期状态（用于清理长期失联的Worker）

        参数：
            timeout_seconds: 超时时间（秒），默认10秒

        返回：
            bool: 节点是否需要被清理

        说明：
            - 仅在节点已被标记为MISSING后使用
            - 结合Redis心跳检查和本地时间戳判断
            - 用于提供宽限期机制，避免立即删除异常断开的Worker
        """
        current_time = time.time()

        # 如果从未收到心跳（last_update为0），认为已过期
        if self.last_update == 0.0:
            return True

        # 检查本地缓存时间是否超时
        return (current_time - self.last_update) > timeout_seconds


# =============================================================================
# 运行器类 - 单机模式
# =============================================================================

class LocalRunner(BaseRunner):
    """
    本地负载测试运行器（单机模式）

    功能职责:
    - 本地用户管理和负载执行
    - Prometheus HTTP 指标服务启动
    - 系统资源监控（CPU、用户数）
    - 测试生命周期管理

    架构特点:
    - 继承 BaseRunner，通过组合模式获得基础组件
    - 集成统一的指标收集器和任务管理器
    - 提供完整的本地测试环境

    组件集成:
    - UserManager: 用户创建、启动和停止
    - TaskManager: 后台监控任务管理
    - StateManager: 状态机管理
    - 统一指标收集器: Prometheus 指标记录

    典型用法:
    1. 使用 RunnerFactory.create("local", ...) 创建实例
    2. 调用 start() 启动负载测试
    3. 调用 stop() 停止测试并清理资源
    """

    def __init__(self, user_types, load_shape, config):
        """
        初始化本地运行器

        参数：
            user_types: 用户类列表
            load_shape: 负载形状类
            config: 配置选项
        """
        # 调用基类初始化
        super().__init__(user_types, load_shape, config)

        # 本地运行器特有属性
        self.node = NODE_TYPE_LOCAL

        # 本地特定的组件
        self.metrics_collector = None
        self.prometheus_server_started = False
        self.prometheus_runner = None

    async def initialize(self):
        """初始化本地运行器特有的组件"""
        # 调用父类的初始化方法，确保 machine_id 被正确初始化
        await super().initialize()

        # 数据收集频率配置
        self.metrics_collection_interval = self.config.metrics_collection_interval  # 默认5秒

        # 初始化统一的指标收集器
        self.metrics_batch_size = self.config.metrics_batch_size  # 默认批量大小 100
        self.metrics_flush_interval = self.config.metrics_flush_interval  # 默认刷新间隔 1秒
        self.metrics_buffer_size = self.config.metrics_buffer_size  # 默认缓冲区大小 10000

        self.metrics_collector = await init_metrics_collector(
            self.node,
            None,
            "local",
            None,
            batch_size=self.metrics_batch_size,
            flush_interval=self.metrics_flush_interval,
            buffer_size=self.metrics_buffer_size
        )

        # 启动 Prometheus HTTP 服务（使用通用方法）
        self.prometheus_runner, self.prometheus_server_started = await start_prometheus_service(self.config, self)

        # 初始化监控任务
        self.task_manager.add_tasks([
            asyncio.create_task(
                self._collect_node_metrics(),
                name="local_node_metrics"),
        ])

    async def stop(self) -> None:
        """停止本地负载测试"""
        if self.state_manager.get_current_state() == RunnerState.READY:
            return

        logger.debug("正在停止本地测试")

        try:
            await self.state_manager.transition_state(RunnerState.STOPPING)

            # 停止指标收集器
            if self.metrics_collector:
                await self.metrics_collector.stop()

            # 停止Prometheus HTTP服务
            if self.prometheus_runner:
                await self.prometheus_runner.cleanup()
                self.prometheus_runner = None
                self.prometheus_server_started = False

            # 停止所有用户
            await self.user_manager.manage_users(user_count=self.active_user_count, rate=100, action="stop")

            # 取消所有后台任务（包括监控任务）
            await self.task_manager.cancel_all_tasks()

            # 触发测试停止事件
            await test_stop.fire(runner=self)

            await self.state_manager.transition_state(RunnerState.READY)

        except Exception as e:
            logger.error("停止失败: %s", str(e))
            raise

    async def _collect_node_metrics(self):
        """本地节点指标收集任务（包含CPU收集和指标上报）"""
        # 启动CPU收集任务
        cpu_task = asyncio.create_task(
            self._collect_cpu_metrics(),
            name="cpu_metrics_collector")

        while not self.state_manager.is_in_quit_state():
            try:
                # 使用统一的收集器记录指标
                if hasattr(
                        self, 'metrics_collector') and self.metrics_collector:
                    node_metrics = {
                        "cpu_percent": self.cpu_usage,
                        "active_users": self.active_user_count,  # LocalRunner直接获取活跃用户数
                        "worker_id": self.node,
                        "machine_id": self.machine_id
                    }
                    await self.metrics_collector.record_node_metrics(node_metrics)
            except Exception as e:
                logger.error("收集本地节点指标失败: %s", str(e))
            finally:
                await asyncio.sleep(self.metrics_collection_interval)

        # 退出时取消CPU收集任务
        if not cpu_task.done():
            cpu_task.cancel()
            try:
                await cpu_task
            except asyncio.CancelledError:
                pass


# =============================================================================
# 运行器类 - 分布式工作节点
# =============================================================================

class WorkerRunner(BaseRunner):
    """
    工作节点运行器

    职责：
    - 接收主节点命令
    - 执行负载测试
    - 上报运行状态
    - 心跳机制
    """

    def __init__(self, user_types, load_shape, config, redis_client):
        """
        初始化工作节点运行器

        参数：
            user_types: 用户类列表
            load_shape: 负载形状类
            config: 配置选项
            redis_client: Redis 客户端（必需）
        """
        super().__init__(user_types, load_shape, config)
        self.node = NODE_TYPE_WORKER
        self.redis_client = redis_client
        self.client_id = str(uuid4())
        self.coordinator = DistributedCoordinator(
            redis_client, role=NODE_TYPE_WORKER, node_id=self.client_id)

    async def _collect_worker_metrics(self) -> None:
        """收集Worker节点的CPU使用率（使用BaseRunner的通用方法）"""
        await self._collect_cpu_metrics()

    @property
    def load_shape_manager(self):
        """Worker不需要负载形状管理器，返回None"""
        return None

    async def initialize(self):
        """初始化工作节点运行器"""
        # 调用父类的初始化方法，确保 machine_id 被正确初始化
        await super().initialize()

        # 数据收集和上传配置
        self.metrics_collection_interval = self.config.metrics_collection_interval  # 默认5秒
        self.metrics_batch_size = self.config.metrics_batch_size  # 默认批量大小 100
        self.metrics_flush_interval = self.config.metrics_flush_interval  # 默认刷新间隔 1秒
        self.metrics_buffer_size = self.config.metrics_buffer_size  # 默认缓冲区大小 10000

        # 初始化统一的指标收集器（Worker模式：需要传递redis_client、node_id和coordinator）
        self.metrics_collector = await init_metrics_collector(
            self.node,
            self.redis_client,
            self.client_id,
            self.coordinator,
            batch_size=self.metrics_batch_size,
            flush_interval=self.metrics_flush_interval,
            buffer_size=self.metrics_buffer_size
        )

        # 启动命令监听任务
        command_listener_task = asyncio.create_task(
            self.coordinator.listen_commands(self._handle_command),
            name="command_listener"
        )

        # 启动心跳、命令处理任务
        self.task_manager.add_tasks([
            asyncio.create_task(
                self._collect_worker_metrics(),
                name="worker_metrics_collector"),
            asyncio.create_task(
                self._send_heartbeat(),
                name="worker_heartbeat_sender"),
            asyncio.create_task(
                self._check_quit_status(),
                name="quit_status_checker"),
            command_listener_task,
        ])

        # Worker节点初始化完成
        logger.info("Worker运行器已初始化，ID: %s", self.client_id)
        
        # 立即发送一次初始心跳，让 Master 快速发现
        try:
            initial_heartbeat = {
                "cpu_percent": 0,
                "active_users": 0,
                "status": str(self.state_manager.get_current_state()),
                "worker_id": self.client_id,
                "machine_id": self.machine_id
            }
            await self.coordinator.publish("heartbeat", initial_heartbeat)
            logger.debug("已发送初始心跳")
        except Exception as e:
            logger.warning("发送初始心跳失败：%s", e)

    async def stop(self) -> None:
        """工作节点停止测试"""
        if not self.state_manager.can_stop():
            current_state = self.state_manager.get_current_state()
            logger.warning(
                "无法从 %s 状态停止，忽略停止请求", current_state)
            return

        await self.state_manager.transition_state(RunnerState.STOPPING)
        try:
            # 停止指标收集器
            if self.metrics_collector:
                await self.metrics_collector.stop()

            # 停止所有用户
            await self.user_manager.stop_all_users()

            await self.state_manager.transition_state(RunnerState.READY)
            await self._send_stop()
            logger.info("Worker %s 已成功停止", self.client_id)
        except Exception as e:
            logger.error("停止失败: %s", str(e), exc_info=True)
        else:
            # 触发测试停止事件
            await test_stop.fire()

    async def _send_heartbeat(self) -> None:
        """心跳发送任务"""
        while not self.state_manager.is_in_quit_state():
            try:
                # 统一使用StateManager的状态，保持一致性
                heartbeat_data = {
                    "cpu_percent": int(self.cpu_usage),
                    "active_users": int(self.active_user_count),
                    "status": str(self.state_manager.get_current_state()),
                    "worker_id": self.client_id,
                    "machine_id": self.machine_id
                }

                # 发送心跳到Redis
                await self.coordinator.publish("heartbeat", heartbeat_data)
                await asyncio.sleep(HEARTBEAT_INTERVAL)
            except Exception as e:
                logger.error("心跳发送错误: %s", str(e))
                await asyncio.sleep(HEARTBEAT_INTERVAL)

    async def _send_startup_completed(self):
        """发送启动完成确认"""
        await self.coordinator.publish(
            "command",
            {"user_count": self.active_user_count},
            worker_id=self.client_id,
            command="startup_completed"
        )

    async def _send_stop(self):
        """发送停止确认"""
        await self.coordinator.publish("command", {}, worker_id=self.client_id, command="stop")

    async def _check_quit_status(self):
        """定期检查退出状态，通过命令通道接收Master节点的quit命令"""
        while not self.state_manager.is_in_quit_state():
            try:
                # 每5秒检查一次退出状态
                await asyncio.sleep(5.0)

            except Exception as e:
                logger.warning("检查退出状态失败: %s", e)
                # 出错后，等待一段时间再继续检查
                await asyncio.sleep(5.0)
                continue

    async def _handle_command(self, data: dict, worker_id: str, command: str):
        """统一的命令处理器"""
        if command == "startup":
            user_count = data.get("user_count", 0) if data else 0
            rate = data.get("rate", 1.0) if data else 1.0
            await self.apply_load(user_count, rate)
        elif command == "stop":
            await self.stop()
        elif command == "quit":
            await self.quit()
        elif command == "pause":
            await self.pause()
        elif command == "resume":
            await self.resume()
        else:
            logger.warning("未知命令: %s", command)

    async def apply_load(self, user_count: int, rate: float) -> None:
        """重写基类方法，添加Worker特定的启动完成通知"""
        try:
            # 调用基类实现
            await super().apply_load(user_count, rate)

            # Worker需要发送特定的启动完成通知（补充基类的全局事件）
            await self._send_startup_completed()
        except Exception as e:
            # 启动失败时也要发送通知，让Master知道Worker已完成启动（即使失败）
            logger.error("Worker启动失败: %s", str(e))
            await self._send_startup_completed()
            raise

    async def quit(self):
        """Worker退出"""
        if self.state_manager.is_in_quit_state():
            return

        # 立即设置退出状态，让主循环能够检测到
        self.state_manager.set_quit_state()
        await self.state_manager.transition_state(RunnerState.QUITTING)

        # 异步停止所有用户和后台任务，不阻塞主循环
        async def stop_tasks():
            try:
                # 停止所有用户
                await self.user_manager.manage_users(user_count=self.active_user_count, rate=100, action="stop")

                # 取消所有后台任务
                await self.task_manager.cancel_all_tasks()

                logger.info("Worker %s 已成功退出", self.client_id)
            except Exception as e:
                logger.error("Worker退出过程中出错: %s", str(e))
                raise

        # 启动一个新任务来停止所有用户和后台任务
        asyncio.create_task(stop_tasks())


# =============================================================================
# 运行器类 - 分布式主节点
# =============================================================================

class MasterRunner:
    """
    主节点运行器（分布式协调器）

    职责：
    - 分布式节点管理
    - 负载分配策略
    - 全局状态协调
    - Worker 节点监控

    注意：不再继承BaseRunner，因为Master节点不直接运行用户
    """

    def __init__(self, user_types, load_shape, config, redis_client):
        """
        初始化主节点运行器

        参数：
            user_types: 用户类列表（用于负载分配计算）
            load_shape: 负载形状类（用于动态负载调整）
            config: 配置选项
            redis_client: Redis 客户端（分布式模式必需）
        """
        self.user_types = user_types
        self.load_shape = load_shape
        self.config = config
        self.node = NODE_TYPE_MASTER
        self.redis_client = redis_client
        self.coordinator = DistributedCoordinator(
            redis_client, role=NODE_TYPE_MASTER)

        # 状态管理（使用统一的StateManager）
        self._state_manager = None

        # Worker 节点管理（使用Redis作为数据源）
        self.workers: Dict[str, WorkerNode] = {}

        # 指标收集
        self.metrics_collector = None
        self.cpu_usage = 0

        # 后台任务
        self.background_tasks: List[asyncio.Task] = []

        # 负载形状管理器
        self._load_shape_manager = None

        # Prometheus服务相关
        self.prometheus_runner = None
        self.prometheus_server_started = False

    @property
    def state_manager(self):
        """获取状态管理器"""
        if self._state_manager is None:
            from aiotest.state_manager import StateManager
            self._state_manager = StateManager()
        return self._state_manager

    @property
    def load_shape_manager(self):
        """获取负载形状管理器"""
        if self._load_shape_manager is None and self.load_shape:
            self._load_shape_manager = LoadShapeManager(
                self.load_shape, self.apply_load)
        return self._load_shape_manager

    async def initialize(self):
        """初始化主节点运行器"""
        # 批量上传配置
        metrics_batch_size = self.config.metrics_batch_size  # 默认批量大小 100
        metrics_flush_interval = self.config.metrics_flush_interval  # 默认刷新间隔 1秒
        metrics_buffer_size = self.config.metrics_buffer_size  # 默认缓冲区大小 10000

        self.metrics_collector = await init_metrics_collector(
            self.node,
            self.redis_client,
            "master",
            self.coordinator,
            batch_size=metrics_batch_size,
            flush_interval=metrics_flush_interval,
            buffer_size=metrics_buffer_size
        )

        # 启动 Prometheus HTTP 服务（使用通用方法）
        self.prometheus_runner, self.prometheus_server_started = await start_prometheus_service(self.config, self)

        # 添加后台任务（使用DistributedCoordinator的统一监听器）
        request_listener_task = asyncio.create_task(
            self.coordinator.listen_request_metrics(
                callback=self._handle_worker_request_metrics),
            name="request_metrics_listener"
        )

        # 启动命令监听任务
        command_listener_task = asyncio.create_task(
            self.coordinator.listen_commands(self._handle_command),
            name="command_listener"
        )

        # 启动节点状态监听任务（负责状态更新和自动发现）
        node_status_task = asyncio.create_task(
            self.coordinator.listen_heartbeats(
                callback=self._update_worker_status),
            name="node_status_listener"
        )

        self.background_tasks.extend([
            request_listener_task,
            command_listener_task,
            node_status_task,
        ])

        # Master节点初始化完成
        logger.info(
            "Master节点初始化完成，ID: %s",
            self.coordinator.node_id)

    async def _handle_worker_request_metrics(
            self, metrics_data: dict, worker_id: str):
        """
        处理Worker上报的请求数据

        参数：
            metrics_data: 请求数据
            worker_id: Worker节点ID
        """
        # 触发worker_request_metrics事件
        await worker_request_metrics.fire(
            data=metrics_data,
            worker_id=worker_id,
            node_type=self.node,
            runner=self
        )

    async def _handle_command(self, data: dict, worker_id: str, command: str):
        """Master节点的统一命令处理器"""
        if command == "startup_completed":
            if hasattr(self, '_startup_completion_tracker'):
                self._startup_completion_tracker["completed_workers"].add(
                    worker_id)
                user_count = data.get("user_count", 0) if data else 0
                logger.info(
                    "Worker %s 已完成启动，用户数: %d", worker_id, user_count)
        elif command == "stop":
            logger.info("Worker %s 已完成停止操作", worker_id)

            # 标记Worker为已停止状态
            if hasattr(self, '_stop_completion_tracker'):
                self._stop_completion_tracker["stopped_workers"].add(worker_id)

            # 检查是否所有Worker都已停止
            if hasattr(self, '_stop_completion_tracker'):
                total_workers = self._stop_completion_tracker["total_workers"]
                stopped_workers = len(
                    self._stop_completion_tracker["stopped_workers"])

                if stopped_workers >= total_workers:
                    logger.info(
                        "所有 %d 个 Worker 已完成停止操作", stopped_workers)
                    # 所有Worker都停止完成，可以安全转换状态和触发事件
                    await self.state_manager.transition_state(RunnerState.READY)
                    await test_stop.fire(runner=self)
        else:
            logger.debug(
                "Master 收到来自 %s 的未知命令: %s", worker_id, command)

    async def apply_load(self, user_count: int, rate: float) -> None:
        """应用负载配置：从load_shape接收用户数和速率后执行"""
        current_state = self.state_manager.get_current_state()

        # 如果是从READY状态启动,需要先转换状态
        if current_state == RunnerState.READY:
            await test_start.fire(runner=self)
            await self.state_manager.transition_state(RunnerState.STARTING)

        try:
            # 如果是首次启动(从READY或STARTING状态),需要等待Worker启动完成
            if current_state in [RunnerState.READY, RunnerState.STARTING]:
                # 设置启动完成跟踪
                self._startup_completion_tracker = {
                    "expected_workers": len(self.workers),
                    "completed_workers": set(),
                    "startup_data": {"user_count": user_count, "rate": rate}
                }

                # 广播启动命令到所有 Worker
                await self._broadcast_startup(user_count, rate)

                # 等待所有Worker启动完成(设置超时)
                await self._wait_for_workers_startup_completion()

                # 所有Worker启动完成后,触发事件
                await startup_completed.fire(runner=self, node_type=self.node)
            else:
                # 已在运行中,直接广播新的负载配置
                logger.info(
                    "调整负载: %d 个用户，速率: %.1f/s",
                    user_count, rate)
                await self._broadcast_startup(user_count, rate)

        except Exception as e:
            # 获取当前实际状态
            actual_state = self.state_manager.get_current_state()
            # 根据实际状态进行相应的状态转换
            if actual_state == RunnerState.READY:
                # 从READY状态启动失败，保持在READY
                pass
            elif actual_state == RunnerState.STARTING:
                # 从STARTING状态失败，转换到STOPPING
                await self.state_manager.transition_state(RunnerState.STOPPING)
            logger.error("Master应用负载失败: %s", str(e))
            raise

    async def _wait_for_workers_startup_completion(
            self, timeout: float = 30.0) -> None:
        """等待所有Worker启动完成"""
        start_time = asyncio.get_event_loop().time()

        # 使用启动时的Worker数量作为预期数量，避免在等待过程中发现新Worker导致的超时
        expected_count = self._startup_completion_tracker.get(
            "expected_workers", 0)

        while not self.state_manager.is_in_quit_state():
            completed_count = len(
                self._startup_completion_tracker["completed_workers"])

            if completed_count >= expected_count and expected_count > 0:
                logger.info(
                    "所有 %d 个 Worker 已完成启动", expected_count)
                break

            # 检查超时
            if asyncio.get_event_loop().time() - start_time > timeout:
                raise RunnerError(
                    f"启动超时: 仅 {completed_count}/{expected_count} 个 Worker 完成")

            logger.debug(
                "等待 Worker 启动: %d/%d 已完成", completed_count, expected_count)
            await asyncio.sleep(0.5)

    async def start(self) -> None:
        """启动测试：使用负载形状管理器执行测试"""
        if not self.load_shape:
            raise ValueError("测试执行需要负载形状")

        # 使用LoadShapeManager启动测试
        await self.load_shape_manager.start()

    async def run_until_complete(self) -> None:
        """运行测试直到完成"""
        if self.load_shape_manager.task:
            await self.load_shape_manager.task

    async def stop(self) -> None:
        """停止分布式负载测试"""
        if not self.state_manager.can_stop():
            return

        await self.state_manager.transition_state(RunnerState.STOPPING)

        try:
            # 停止指标收集器
            if self.metrics_collector:
                await self.metrics_collector.stop()

            # 停止Prometheus HTTP服务
            if self.prometheus_runner:
                await self.prometheus_runner.cleanup()
                self.prometheus_runner = None
                self.prometheus_server_started = False

            # 初始化停止完成跟踪器
            healthy_workers = await self.get_healthy_workers()
            self._stop_completion_tracker = {
                "stopped_workers": set(),
                "total_workers": len(healthy_workers)
            }

            # 广播停止命令
            await self.coordinator.publish("command", {}, command="stop")

            logger.info(
                "已发送停止命令到 %d 个 Worker",
                self._stop_completion_tracker['total_workers'])

            # 不立即转换状态和触发事件，等待所有Worker确认完成

        except Exception as e:
            logger.error("Master停止失败: %s", str(e))
            raise

    async def quit(self):
        """退出主节点并通知所有Worker停止"""
        if self.state_manager.is_in_quit_state():
            return

        # 停止负载形状管理器
        if self._load_shape_manager:
            await self._load_shape_manager.stop()

        # 先通知所有Worker节点退出
        try:
            await self.coordinator.publish("command", {}, command="quit")
        except Exception as e:
            logger.warning("发送退出命令到Worker失败: %s", e)

        # 设置退出状态
        self.state_manager.set_quit_state()
        await self.state_manager.transition_state(RunnerState.QUITTING)

        # 停止指标收集器
        if self.metrics_collector:
            await self.metrics_collector.stop()

        # 停止Prometheus HTTP服务
        if self.prometheus_runner:
            await self.prometheus_runner.cleanup()
            self.prometheus_runner = None
            self.prometheus_server_started = False

        # 取消所有后台任务
        for task in self.background_tasks:
            if not task.done():
                task.cancel()

        if self.background_tasks:
            await asyncio.gather(*self.background_tasks, return_exceptions=True)
            self.background_tasks.clear()

        logger.info("Master运行器已成功退出")

    async def pause(self) -> None:
        """暂停测试"""
        if not self.state_manager.can_pause():
            current_state = self.state_manager.get_current_state()
            logger.warning("无法从 %s 状态暂停，忽略暂停请求", current_state)
            return

        await self.state_manager.transition_state(RunnerState.PAUSED)
        # 向所有Worker发送pause命令
        try:
            await self.coordinator.publish("command", {}, command="pause")
        except Exception as e:
            logger.warning("发送暂停命令到Worker失败: %s", e)
        logger.info("测试已暂停")

    async def resume(self) -> None:
        """恢复测试"""
        if not self.state_manager.can_resume():
            current_state = self.state_manager.get_current_state()
            logger.warning("无法从 %s 状态恢复，忽略恢复请求", current_state)
            return

        await self.state_manager.transition_state(RunnerState.RUNNING)
        # 向所有Worker发送resume命令
        try:
            await self.coordinator.publish("command", {}, command="resume")
        except Exception as e:
            logger.warning("发送恢复命令到Worker失败: %s", e)
        logger.info("测试已恢复")

    def _distribute_resources(self, total_value: int,
                              total_workers: int) -> List[int]:
        """
        将总资源均匀分配给所有 Worker 节点

        参数：
            total_value: 总资源值（用户数或速率）
            total_workers: Worker 节点总数

        返回：
            List[int]: 每个 Worker 分配的资源值列表
        """
        if total_workers == 0:
            return []

        # 基础分配值
        base_value = total_value // total_workers
        # 剩余资源
        remainder = total_value % total_workers

        distribution = []
        for i in range(total_workers):
            # 基础分配 + 前几个Worker各分配1单位剩余资源
            assigned_value = base_value + (1 if i < remainder else 0)
            distribution.append(assigned_value)

        return distribution

    async def _broadcast_startup(self, user_count: int, rate: float) -> None:
        """广播启动命令到所有 Worker 节点"""
        if not self.workers:
            raise RunnerError("No ready workers available")

        total_workers = len(self.workers)

        # 计算分配方案
        user_distribution = self._distribute_resources(
            user_count, total_workers)
        rate_distribution = self._distribute_resources(
            int(rate), total_workers)

        # 为每个 Worker 发送启动命令
        worker_ids = sorted(self.workers.keys())
        for i, worker_id in enumerate(worker_ids):
            startup_data = {
                "user_count": user_distribution[i],
                "rate": rate_distribution[i]
            }

            # 发送给指定的 Worker
            await self.coordinator.publish("command", startup_data, worker_id=worker_id, command="startup")

    async def _update_worker_status(
            self, heartbeat_data: dict, worker_id: str):
        """
        更新Worker状态和指标数据（包含自动发现）

        参数：
            heartbeat_data: Worker心跳数据（包含CPU、用户数、状态等）
            worker_id: Worker节点ID
        """
        # 自动发现新Worker
        if worker_id not in self.workers:
            worker = WorkerNode(worker_id)
            self.workers[worker_id] = worker
            logger.info("已发现并注册新的Worker: %s", worker_id)

        # 更新本地Worker状态缓存
        worker = self.workers[worker_id]
        worker.update_from_heartbeat(heartbeat_data)

        # 记录Worker指标到Prometheus
        if self.metrics_collector:
            await self.metrics_collector.record_node_metrics(heartbeat_data)

    async def get_healthy_workers(self) -> List[WorkerNode]:
        """
        获取所有健康的Worker节点（包含按需清理）

        逻辑：
        1. 检查节点状态是否健康（READY/RUNNING/STARTING/STOPPING）
        2. 通过 DistributedCoordinator 检查节点心跳状态
        3. 清理长期失联的Worker（避免内存泄漏）
        """
        healthy_workers = []
        workers_to_remove = []

        for node_id, worker in list(self.workers.items()):
            try:
                # 通过 Redis 检查实际心跳状态
                is_alive = await self.coordinator.check_worker_heartbeat(node_id)

                if is_alive:
                    # 节点存活，检查状态是否健康
                    if worker.status in [
                            RunnerState.READY, RunnerState.RUNNING, RunnerState.STARTING, RunnerState.STOPPING]:
                        healthy_workers.append(worker)
                else:
                    # 节点失联，处理状态和清理
                    if worker.status != RunnerState.MISSING:
                        worker.status = RunnerState.MISSING
                        logger.warning("Worker %s 被标记为丢失", node_id)
                    else:
                        # 已经是丢失状态，检查是否需要移除
                        if worker.is_stale(60.0):  # 给Worker恢复机会
                            workers_to_remove.append(node_id)
                            logger.warning(
                                "Worker %s 超时后将被移除", node_id)

            except Exception as e:
                logger.warning("检查 %s 的心跳失败: %s", node_id, e)

        # 清理超时的死亡worker
        for node_id in workers_to_remove:
            del self.workers[node_id]
            logger.info("Worker %s 超时后已被移除", node_id)

        return healthy_workers
