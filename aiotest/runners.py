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
    test_quit,
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
from aiotest.task_manager import TaskManager

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

    # HTML 内容在创建应用时读取一次并缓存，
    # 避免每次请求都同步执行文件 I/O 阻塞事件循环
    import os
    static_dir = os.path.join(os.path.dirname(__file__), 'static')
    html_path = os.path.join(static_dir, 'index.html')
    html_content = None
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except Exception as e:
        logger.error("读取HTML文件失败: %s", str(e))

    async def index_handler(_):
        """处理根路径，返回Web控制界面"""
        if html_content is None:
            return web.Response(body=b'Error loading control page', status=500)
        return web.Response(text=html_content, content_type='text/html')

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
    # 重复初始化时 init_unified_collector 会先停止旧收集器注销其事件处理器
    return await init_unified_collector(
        node,
        redis_client,
        node_id,
        coordinator,
        batch_size=batch_size,
        flush_interval=flush_interval,
        buffer_size=buffer_size
    )


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
    return prometheus_runner


# =============================================================================
# 数据类
# =============================================================================

class WorkerNode:
    """Master 端缓存的工作节点状态镜像（纯数据结构，无心跳逻辑）。

    失联节点由 get_healthy_workers() 按需清理：先标记 MISSING，60 秒宽限期后删除。
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
    """本地负载测试运行器（单机模式）。

    在 BaseRunner 基础上增加本地指标收集与 Prometheus HTTP 指标服务。
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

        # 初始化统一的指标收集器
        await self._init_metrics(redis_client=None, node_id="local", coordinator=None)

        # 启动 Prometheus HTTP 服务（使用通用方法）
        self.prometheus_runner = await start_prometheus_service(self.config, self)
        self.prometheus_server_started = True

    async def start(self) -> None:
        """启动本地测试"""
        # 先调用父类启动逻辑
        await super().start()

        # 启动指标收集任务（在 start() 中启动，而非 initialize()）
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

            # 停止负载形状管理器：形状任务不在 task_manager 中，
            # cancel_all_tasks 无法停止它；若不停止，STOPPING 后形状仍会
            # 继续 tick 并触发 apply_load 重新拉起用户，导致停止失效
            if self._load_shape_manager:
                await self._load_shape_manager.stop()

            # 停止指标收集器
            if self.metrics_collector:
                await self.metrics_collector.stop()

            # 停止Prometheus HTTP服务
            if self.prometheus_runner:
                await self.prometheus_runner.cleanup()
                self.prometheus_runner = None
                self.prometheus_server_started = False

            # 停止所有用户
            await self.user_manager.stop_all_users()

            # 取消所有后台任务（包括监控任务）
            await self.task_manager.cancel_all_tasks()

            await self.state_manager.transition_state(RunnerState.READY)

        except Exception as e:
            logger.error("停止失败: %s", str(e))
            raise
        finally:
            # 无论成功或失败都触发 test_stop 事件，与 WorkerRunner 行为一致
            await test_stop.fire(runner=self)

    async def _collect_node_metrics(self):
        """本地节点指标收集任务（包含CPU收集和指标上报）"""
        # 启动CPU收集任务
        cpu_task = asyncio.create_task(
            self._collect_cpu_metrics(),
            name="cpu_metrics_collector")

        try:
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
        finally:
            # cpu_task 未纳入 task_manager，stop()→cancel_all_tasks 取消本任务时
            # CancelledError 会跳过循环后的清理；用 try/finally 保证无论正常退出
            # 还是被取消都回收 CPU 子任务，避免其孤儿运行（stop 不置 is_quit）
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
    """工作节点运行器：接收主节点命令、执行负载并上报心跳与运行状态。"""

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

        # 命令监听器订阅完成信号：心跳首轮发送前等待，避免启动命令丢失
        self._command_ready = asyncio.Event()

    @property
    def load_shape_manager(self):
        """Worker不需要负载形状管理器，返回None"""
        return None

    async def initialize(self):
        """初始化工作节点运行器（只做配置，不启动后台任务）"""
        # 调用父类的初始化方法，确保 machine_id 被正确初始化
        await super().initialize()

        # 初始化统一的指标收集器（Worker模式：需要传递redis_client、node_id和coordinator）
        await self._init_metrics(
            redis_client=self.redis_client,
            node_id=self.client_id,
            coordinator=self.coordinator
        )

        # 保存协程引用，在 start() 中统一启动，避免 initialize 阶段就开始采集数据
        self._command_listener_coro = self.coordinator.listen_commands(
            self._handle_command, ready_event=self._command_ready)
        self._pending_background_tasks = [
            (self._collect_cpu_metrics, "worker_metrics_collector"),
            (self._send_heartbeat, "worker_heartbeat_sender"),
        ]

        # Worker节点初始化完成
        logger.info("Worker运行器已初始化，ID: %s", self.client_id)

    async def start(self) -> None:
        """启动Worker后台任务（心跳发送、命令监听、CPU采集等）"""

        # 在 start() 中启动后台任务，而非 initialize()
        tasks = [
            asyncio.create_task(coro(), name=name)
            for coro, name in self._pending_background_tasks
        ]
        tasks.append(asyncio.create_task(self._command_listener_coro, name="command_listener"))
        self.task_manager.add_tasks(tasks)
        logger.info("Worker %s 后台任务已启动（心跳、命令监听等）", self.client_id)

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
        finally:
            # 触发测试停止事件
            await test_stop.fire()

    async def _send_heartbeat(self) -> None:
        """心跳发送任务"""
        # 等待命令监听器完成订阅后再发送首轮心跳：
        # 心跳一旦被Master观测到，Master可能立即广播启动命令，
        # 若Worker尚未订阅命令频道，启动命令将丢失
        command_ready = getattr(self, "_command_ready", None)
        if command_ready:
            try:
                await asyncio.wait_for(
                    command_ready.wait(), timeout=HEARTBEAT_INTERVAL * 5)
            except asyncio.TimeoutError:
                # 订阅异常时兜底继续发心跳，避免Worker永远不可见
                logger.error("命令监听器订阅超时，启动命令可能丢失")

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



# =============================================================================
# 运行器类 - 分布式主节点
# =============================================================================

class MasterRunner:
    """主节点运行器（分布式协调器）：管理 Worker 节点、分配负载、协调全局状态。

    不继承 BaseRunner——Master 不直接运行用户。
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

        # 后台任务（与 BaseRunner 一致，由 TaskManager 统一管理）
        self.task_manager = TaskManager()

        # 负载形状管理器
        self._load_shape_manager = None

        # 停止流程幂等收尾标志（_handle_command 全部确认与超时看门狗共用）
        self._stop_finalized = False

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
        self.metrics_batch_size = self.config.metrics_batch_size
        self.metrics_flush_interval = self.config.metrics_flush_interval
        self.metrics_buffer_size = self.config.metrics_buffer_size

        self.metrics_collector = await init_metrics_collector(
            self.node,
            self.redis_client,
            "master",
            self.coordinator,
            batch_size=self.metrics_batch_size,
            flush_interval=self.metrics_flush_interval,
            buffer_size=self.metrics_buffer_size,
        )

        # 启动 Prometheus HTTP 服务（使用通用方法）
        self.prometheus_runner = await start_prometheus_service(self.config, self)
        self.prometheus_server_started = True

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

        self.task_manager.add_tasks([
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
                total_workers = self._stop_completion_tracker["total_workers"]
                stopped_workers = len(
                    self._stop_completion_tracker["stopped_workers"])

                if stopped_workers >= total_workers:
                    logger.info(
                        "所有 %d 个 Worker 已完成停止操作", stopped_workers)
                    # 全部Worker确认完成，幂等收尾（与超时看门狗共用同一出口）
                    await self._finalize_stop()
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
                # 过滤出健康 Worker（心跳存活且状态非 MISSING）：
                # 失联节点收不到启动命令，将其计入预期会导致启动超时
                healthy_workers = await self.get_healthy_workers()

                # 设置启动完成跟踪
                self._startup_completion_tracker = {
                    "expected_workers": len(healthy_workers),
                    "completed_workers": set(),
                    "startup_data": {"user_count": user_count, "rate": rate}
                }

                # 广播启动命令到所有健康 Worker
                await self._broadcast_startup(
                    user_count, rate, healthy_workers=healthy_workers)

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
            elif actual_state == RunnerState.RUNNING:
                # 从RUNNING状态失败，转换到STOPPING
                logger.warning("RUNNING 状态下应用负载失败，转换到 STOPPING")
                await self.state_manager.transition_state(RunnerState.STOPPING)
            logger.error("Master应用负载失败: %s", str(e))
            raise

    async def _wait_for_workers_startup_completion(
            self, timeout: float = 30.0) -> None:
        """等待所有Worker启动完成"""
        start_time = asyncio.get_running_loop().time()

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
            if asyncio.get_running_loop().time() - start_time > timeout:
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
        if self.load_shape_manager and self.load_shape_manager.task:
            await self.load_shape_manager.task

    async def stop(self) -> None:
        """停止分布式负载测试"""
        if not self.state_manager.can_stop():
            return

        await self.state_manager.transition_state(RunnerState.STOPPING)

        try:
            # 停止负载形状管理器：形状任务不在 task_manager 中，
            # 若不停止，STOPPING 期间形状仍会广播启动命令给 Worker，
            # 导致停止失效、测试被重新拉起
            if self._load_shape_manager:
                await self._load_shape_manager.stop()

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
            self._stop_finalized = False
            self._stop_completion_tracker = {
                "stopped_workers": set(),
                "total_workers": len(healthy_workers)
            }

            # 广播停止命令
            await self.coordinator.publish("command", {}, command="stop")

            logger.info(
                "已发送停止命令到 %d 个 Worker",
                self._stop_completion_tracker['total_workers'])

            if not healthy_workers:
                # 无健康Worker：无人会回停止确认，直接幂等收尾，
                # 避免 total_workers=0 时永久卡在 STOPPING
                await self._finalize_stop()
            else:
                # 有Worker：启动超时看门狗兜底，防止个别Worker在确认前失联
                # 导致计数永远差一个而永久卡死；全部确认时 _handle_command
                # 会提前幂等收尾，看门狗检测到 _stop_finalized 后随即退出
                watchdog = asyncio.create_task(
                    self._watch_stop_completion(),
                    name="stop_completion_watchdog")
                self.task_manager.add_task(watchdog)

        except Exception as e:
            logger.error("Master停止失败: %s", str(e))
            raise

    async def _finalize_stop(self) -> None:
        """幂等收尾停止流程：转 READY 并触发 test_stop（仅执行一次）。

        _handle_command（全部Worker确认）与 _watch_stop_completion（超时兜底）
        共用此出口；_stop_finalized 在首个 await 之前同步置位，避免两条路径
        并发重复转换状态/重复触发事件。
        """
        if self._stop_finalized:
            return
        self._stop_finalized = True
        if self.state_manager.get_current_state() == RunnerState.STOPPING:
            await self.state_manager.transition_state(RunnerState.READY)
            await test_stop.fire(runner=self)

    async def _watch_stop_completion(self, timeout: float = 30.0) -> None:
        """停止确认超时看门狗：超时仍未收尾则强制完成，避免永久卡在 STOPPING。"""
        start_time = asyncio.get_running_loop().time()
        try:
            while not self._stop_finalized and not self.state_manager.is_in_quit_state():
                if asyncio.get_running_loop().time() - start_time > timeout:
                    logger.warning(
                        "Worker停止确认超时(%.0fs)，强制完成停止流程", timeout)
                    await self._finalize_stop()
                    return
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
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

        # 设置退出状态（is_quit 标志是退出真相，
        # 置位后 transition_state 会早退，无需再转换状态）
        self.state_manager.set_quit_state()

        # 停止指标收集器
        if self.metrics_collector:
            await self.metrics_collector.stop()

        # 停止Prometheus HTTP服务
        if self.prometheus_runner:
            await self.prometheus_runner.cleanup()
            self.prometheus_runner = None
            self.prometheus_server_started = False

        # 取消所有后台任务（与 BaseRunner 一致，由 TaskManager 统一管理）
        await self.task_manager.cancel_all_tasks()

        # 触发测试退出事件（quit 入口有 is_quit 早退保护，不会重复触发）
        await test_quit.fire(runner=self)

        logger.info("Master运行器已成功退出")

    async def pause(self) -> None:
        """暂停测试"""
        if not self.state_manager.can_pause():
            current_state = self.state_manager.get_current_state()
            logger.warning("无法从 %s 状态暂停，忽略暂停请求", current_state)
            return

        await self.state_manager.transition_state(RunnerState.PAUSED)
        # 暂停负载形状的计时
        if self.load_shape and hasattr(self.load_shape, 'pause'):
            self.load_shape.pause()
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
        # 恢复负载形状的计时
        if self.load_shape and hasattr(self.load_shape, 'resume'):
            self.load_shape.resume()
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

    def _distribute_rate(self, rate: float, total_workers: int) -> List[float]:
        """
        将总速率均匀分配给所有 Worker 节点（保留小数精度）

        参数：
            rate: 总速率（用户/秒）
            total_workers: Worker 节点总数

        返回：
            List[float]: 每个 Worker 分配的速率列表，总和精确等于 rate
        """
        if total_workers == 0:
            return []

        base_rate = rate / total_workers
        distribution = [base_rate] * total_workers
        # 舍入误差补偿：最后一个 Worker 承担余数，保证总和精确等于 rate
        distribution[-1] = rate - base_rate * (total_workers - 1)
        return distribution

    async def _broadcast_startup(
            self, user_count: int, rate: float,
            healthy_workers: List['WorkerNode'] = None) -> None:
        """
        广播启动命令到所有健康 Worker 节点

        参数：
            healthy_workers: 健康 Worker 列表。为 None 时内部通过
                get_healthy_workers() 获取（含心跳检查，过滤失联节点）。
        """
        # 过滤失联 Worker：它们收不到启动命令，计入分配会丢失用户数、
        # 计入等待会拖到启动超时
        if healthy_workers is None:
            healthy_workers = await self.get_healthy_workers()
        if not healthy_workers:
            raise RunnerError("No ready workers available")

        total_workers = len(healthy_workers)

        # 校验：每个Worker至少能分到1个用户，否则报错退出。
        # 发送 user_count=0 会在Worker端触发参数校验失败，
        # 而异常路径仍上报启动完成，导致启动"假成功"
        if user_count < total_workers:
            raise RunnerError(
                f"用户数({user_count})少于健康Worker数({total_workers})，"
                "无法为每个Worker分配至少1个用户，"
                "请增加用户数或减少Worker数量")

        # 计算分配方案
        user_distribution = self._distribute_resources(
            user_count, total_workers)
        # 速率按浮点均分，避免 int() 截断导致部分 Worker 速率为 0
        rate_distribution = self._distribute_rate(rate, total_workers)

        # 为每个健康 Worker 发送启动命令
        worker_ids = sorted(worker.node_id for worker in healthy_workers)
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
        1. 检查节点状态是否健康（READY/RUNNING/STARTING/STOPPING/PAUSED）
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
                    # 节点存活，检查状态是否健康。
                    if worker.status in [
                            RunnerState.READY, RunnerState.RUNNING,
                            RunnerState.STARTING, RunnerState.STOPPING,
                            RunnerState.PAUSED]:
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
