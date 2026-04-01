# encoding: utf-8

import asyncio
import json
from typing import Optional
from uuid import uuid4

from redis.asyncio import Redis
from redis.asyncio.connection import ConnectionPool

from aiotest.logger import logger

# 心跳相关常量
HEARTBEAT_INTERVAL = 1.0  # 心跳监控时间间隔(秒)
HEARTBEAT_LIVENESS = 5    # 心跳存活检查次数

# 批量传输相关常量
MAX_BATCH_SIZE = 1000     # 最大批量大小，防止消息过大


class RedisConnection:
    """
    Redis连接管理器

    功能：
        - 管理Redis连接池
        - 提供单例模式的Redis客户端
        - 处理连接异常和重连
        - 支持连接重试机制和指数退避策略
    """

    def __init__(self, max_retries: int = 3, retry_interval: float = 1.0):
        """
        初始化Redis连接管理器

        参数：
            max_retries: 最大重试次数，默认3次
            retry_interval: 初始重试间隔（秒），默认1秒，后续使用指数退避
        """
        self._pool: Optional[ConnectionPool] = None
        self._client: Optional[Redis] = None
        self.max_retries = max_retries
        self.retry_interval = retry_interval

    async def get_client(self, path: str, port: int, password: str) -> Redis:
        """
        获取 Redis 连接实例。

        参数：
            path (str): Redis 服务器地址。
            port (int): Redis 服务器端口。
            password (str): Redis 服务器密码。

        返回：
            Redis: Redis 客户端实例。

        异常：
            redis.ConnectionError: 如果连接 Redis 失败。
        """
        if self._client is None:
            logger.debug("正在创建新的Redis连接，地址: %s:%s", path, port)
            retry_count = 0
            while retry_count < self.max_retries:
                try:
                    if self._pool is None:
                        logger.debug(
                            "创建新的连接池: %s:%s", path, port)
                        self._pool = ConnectionPool.from_url(
                            f"redis://:{password}@{path}:{port}/0",
                            decode_responses=True
                        )
                    self._client = Redis(connection_pool=self._pool)
                    # 测试连接是否可用
                    logger.debug("正在测试Redis连接，地址: %s:%s", path, port)
                    await self._client.ping()
                    logger.info("Redis连接已建立: %s:%s", path, port)
                    return self._client
                except Exception as e:
                    # 重置连接状态以便重试
                    self._pool = None
                    self._client = None
                    retry_count += 1
                    if retry_count < self.max_retries:
                        # 使用指数退避策略：每次重试间隔翻倍
                        backoff_interval = self.retry_interval * \
                            (2 ** (retry_count - 1))
                        logger.warning(
                            "Redis 连接失败 (尝试 %d/%d): %s。%.2f 秒后重试...",
                            retry_count, self.max_retries, str(e), backoff_interval)
                        await asyncio.sleep(backoff_interval)
                    else:
                        logger.error(
                            "Redis 连接失败，已重试 %d 次: %s",
                            self.max_retries, str(e))
                        raise e
        logger.debug("正在使用现有的Redis连接: %s:%s", path, port)
        return self._client

    async def close(self):
        """关闭Redis连接"""
        if self._client:
            await self._client.close()
        if self._pool:
            await self._pool.disconnect()
        self._client = None
        self._pool = None
        logger.info("Redis连接已关闭")


class DistributedLock:
    """
    Redis 分布式锁。

    功能：
        - 提供基于 Redis 的分布式锁机制。
        - 支持超时和重试机制，防止死锁。

    示例：
        >>> lock = DistributedLock(redis_client, "resource_name", timeout=10)
        >>> async with await lock:
        ...     # 临界区代码
        ...     pass

    参数：
        redis (Redis): Redis 客户端实例。
        lock_key (str): 锁的键名。
        timeout (float): 锁的超时时间（秒）。
        wait_timeout (float): 获取锁的等待超时（秒）。
        retry_interval (float): 获取锁失败后的重试间隔（秒）。
    """

    def __init__(
        self,
        redis: Redis,
        lock_key: str,
        timeout: float = 10.0,
        wait_timeout: float = None,
        retry_interval: float = 0.1
    ):
        """
        初始化分布式锁

        参数:
            redis: Redis 客户端实例
            lock_key: 锁的键名
            timeout: 锁的超时时间(秒)，防止死锁
            wait_timeout: 获取锁的等待超时(秒)，None表示不等待
            retry_interval: 获取锁失败后的重试间隔(秒)
        """
        self.redis = redis
        self.lock_key = f"aiotest:lock:{lock_key}"
        self.timeout = timeout
        self.wait_timeout = wait_timeout
        self.retry_interval = retry_interval
        self.identifier = str(uuid4())
        self.locked = False

    async def acquire(self) -> bool:
        """
        获取分布式锁

        返回:
            bool: 是否成功获取锁
        """
        start_time = asyncio.get_event_loop().time()

        while True:
            # 尝试获取锁 (SET lock_key identifier NX PX timeout)
            acquired = await self.redis.set(
                self.lock_key,
                self.identifier,  # 唯一标识，这是我加的锁
                nx=True,  # 只有当key不存在时才设置
                px=int(self.timeout * 1000)  # 过期时间（毫秒）
            )

            if acquired:
                self.locked = True
                return True

            # 如果不等待或已超时，则返回失败
            if self.wait_timeout is None:
                return False

            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= self.wait_timeout:
                return False

            # 没获取到锁，等待后重试
            await asyncio.sleep(self.retry_interval)

    async def release(self) -> bool:
        """
        释放分布式锁

        返回:
            bool: 是否成功释放锁
        """
        if not self.locked:
            return False

        # 使用Lua脚本保证原子性操作
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """

        released = await self.redis.eval(
            lua_script,
            1,
            self.lock_key,
            self.identifier
        )

        if released:
            self.locked = False
            return True
        return False

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # 参数必须保留，即使不使用（异步上下文管理器协议要求）
        await self.release()

    @staticmethod
    async def with_lock(
        redis: Redis,
        lock_key: str,
        timeout: float = 10.0,
        wait_timeout: float = None
    ):
        """
        锁的快捷使用方式

        示例:
            >>> async with await DistributedLock.with_lock(redis, "my_lock_key") as lock:
            ...     if lock.locked:
            ...         # 临界区代码
            ...         pass
        """
        lock = DistributedLock(redis, lock_key, timeout, wait_timeout)
        await lock.acquire()

        # 返回一个不会重复 acquire 的上下文管理器
        return DistributedLock._LockContext(lock)

    class _LockContext:
        """内部上下文管理器，用于 with_lock 方法"""

        def __init__(self, lock: 'DistributedLock'):
            self.lock = lock

        async def __aenter__(self):
            return self.lock

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            # 参数必须保留，即使不使用（异步上下文管理器协议要求）
            await self.lock.release()


class DistributedCoordinator:
    """
    分布式协调器，基于 Redis 的发布/订阅机制实现跨节点的通信。

    功能：
    1. 统一发布系统：支持命令、指标、心跳数据的发布
    2. 监听系统：监听命令、请求指标和心跳数据
    3. 心跳检查：检查Worker节点存活状态

    使用场景：
    - 分布式任务调度
    - 多节点协同操作
    - 实时事件通知
    - 节点健康监控

    示例：
        >>> coordinator = DistributedCoordinator(redis_client, role="master")
        >>> async def handle_command(data, worker_id, command):
        ...     print(f"Received command: {command}, data: {data}, from: {worker_id}")
        >>> task = asyncio.create_task(coordinator.listen_commands(handle_command))
        >>>
        >>> # 发布命令
        >>> await coordinator.publish("command", {"task_id": 123}, command="start_task")
        >>> await coordinator.publish("command", {"reason": "maintenance"}, worker_id="worker_1", command="stop")
        >>>
        >>> # 发送心跳
        >>> await coordinator.publish("heartbeat", {"cpu_percent": 45.0, "active_users": 100})
        >>>
        >>> # 发布请求指标
        >>> await coordinator.publish("request_metrics", request_data, worker_id="worker_1")
        >>>
        >>> # Master监听
        >>> heartbeat_task = asyncio.create_task(coordinator.listen_heartbeats(handle_heartbeat))
    """

    def __init__(self, redis: Redis, role: str = "master",
                 node_id: str = None):
        """
        初始化分布式协调器。

        参数：
            redis: Redis 客户端实例，用于发布/订阅消息。
            role: 节点角色，可选值为 "master" 或 "worker"。
            node_id: 节点ID，可选。
        """
        self.redis = redis
        self.role = role
        self.node_id = node_id or f"{role}_{id(self)}"
        self.pubsub = None
        self.handler = None

        # 根据角色确定订阅和发布的频道
        if role == "master":
            self.subscribe_channel = "aiotest:command:worker_to_master"  # 订阅Worker发来的消息
            self.publish_channel = "aiotest:command:master_to_worker"  # 发布给Worker的消息
        elif role == "worker":
            self.subscribe_channel = "aiotest:command:master_to_worker"  # 订阅Master发来的消息
            self.publish_channel = "aiotest:command:worker_to_master"  # 发布给Master的消息
        else:
            raise ValueError("无效的角色。必须是 'master' 或 'worker'。")

    async def publish(self, channel_type: str, data: dict,
                      worker_id: str = None, **kwargs):
        """
        统一的数据发布方法，支持多种数据类型的发布

        参数：
            channel_type: 频道类型，支持 "command", "request_metrics", "heartbeat"
            data: 要发布的数据字典
            worker_id: Worker节点ID
                       - command: 可选，用于指定目标worker
                       - request_metrics: 必需
                       - heartbeat: 不使用（使用self.node_id）
            **kwargs: 额外参数，如command参数用于命令发布

        返回：
            None

        使用示例：
            # 发布命令
            await coordinator.publish("command", {"reason": "maintenance"}, worker_id="worker_1", command="stop")

            # 发布批量请求指标
            await coordinator.publish("request_metrics", batch_data, worker_id="worker_1")

            # 发送心跳
            await coordinator.publish("heartbeat", {"cpu_percent": 45.0, "active_users": 100})
        """
        if channel_type == "command":
            # 发布命令到命令频道
            command = kwargs.get("command")
            if not command:
                raise ValueError(
                    "命令发布需要 'command' 参数")

            payload = {"command": command}
            if data:
                payload["data"] = data
            if worker_id:
                payload["worker_id"] = worker_id
            await self.redis.publish(self.publish_channel, json.dumps(payload))

        elif channel_type == "request_metrics":
            # 发布批量请求数据到请求指标频道
            if not worker_id:
                raise ValueError(
                    "请求指标批量发布需要 'worker_id'")

            # 如果批量数据过大，拆分成多个小批次发送
            if isinstance(data, list) and len(data) > MAX_BATCH_SIZE:
                for i in range(0, len(data), MAX_BATCH_SIZE):
                    batch_chunk = data[i:i + MAX_BATCH_SIZE]
                    batch_dict = {
                        'batch': batch_chunk,
                        'worker_id': worker_id,
                        'timestamp': asyncio.get_event_loop().time(),
                        'chunk_index': i // MAX_BATCH_SIZE,
                        'total_chunks': (len(data) + MAX_BATCH_SIZE - 1) // MAX_BATCH_SIZE
                    }
                    await self.redis.publish("aiotest:metrics", json.dumps(batch_dict))
            else:
                batch_dict = {
                    'batch': data,
                    'worker_id': worker_id,
                    'timestamp': asyncio.get_event_loop().time()
                }
                await self.redis.publish("aiotest:metrics", json.dumps(batch_dict))

        elif channel_type == "heartbeat":
            # 发送心跳数据（存储到Redis hash，不是发布）
            heartbeat_data = {
                **data,
                "timestamp": int(data.get('timestamp', asyncio.get_event_loop().time()))
            }

            # 将心跳数据存储到Redis，设置过期时间
            heartbeat_key = f"aiotest:heartbeat:{self.node_id}"
            await self.redis.hset(heartbeat_key, mapping=heartbeat_data)
            await self.redis.expire(heartbeat_key, int(HEARTBEAT_INTERVAL * HEARTBEAT_LIVENESS * 2))

        else:
            raise ValueError("不支持的 channel_type: %s", channel_type)

    async def check_worker_heartbeat(self, worker_id: str) -> bool:
        """
        检查特定Worker的心跳状态（Master端使用）

        参数：
            worker_id: Worker节点ID

        返回：
            bool: Worker是否存活
        """
        heartbeat_key = f"aiotest:heartbeat:{worker_id}"
        heartbeat_data = await self.redis.hgetall(heartbeat_key)

        if not heartbeat_data:
            return False

        try:
            current_time = asyncio.get_event_loop().time()
            last_heartbeat = float(heartbeat_data.get("timestamp", 0))
            return (current_time - last_heartbeat) <= HEARTBEAT_INTERVAL * \
                HEARTBEAT_LIVENESS
        except (ValueError, TypeError):
            return False

    async def listen_heartbeats(self, callback=None):
        """
        监听Worker心跳数据变化（Master端使用）

        参数：
            callback: 可选的回调函数，格式为 async def callback(heartbeat_data: dict, worker_id: str)
        """
        # 注意：Redis的心跳数据是存储在hash中的，不是通过pub/sub发布的
        # 所以这里提供轮询检查心跳变化的机制
        worker_status = {}  # 记录上一次的worker状态

        try:
            while True:
                try:
                    heartbeat_keys = []
                    cursor = 0
                    while True:
                        cursor, keys = await self.redis.scan(cursor, match="aiotest:heartbeat:*", count=100)
                        heartbeat_keys.extend(keys)
                        if cursor == 0:
                            break

                    for key in heartbeat_keys:
                        worker_id = key.replace("aiotest:heartbeat:", "")
                        heartbeat_data = await self.redis.hgetall(key)

                        if heartbeat_data:
                            # 检查状态是否发生变化
                            if worker_id not in worker_status or worker_status[worker_id] != heartbeat_data:
                                worker_status[worker_id] = heartbeat_data

                                # 调用回调函数（如果提供）
                                if callback:
                                    await callback(heartbeat_data, worker_id)

                    await asyncio.sleep(HEARTBEAT_INTERVAL)

                except asyncio.CancelledError:
                    # 任务被取消，记录日志并退出
                    logger.info("心跳监听器任务已取消")
                    raise
                except Exception as e:
                    logger.error("心跳监听器错误: %s", str(e))
                    await asyncio.sleep(HEARTBEAT_INTERVAL)
        except asyncio.CancelledError:
            # 任务被取消，记录日志并退出
            logger.info("心跳监听器已停止")
            raise

    async def listen_request_metrics(self, callback=None):
        """
        监听Worker上报的请求数据

        参数：
            callback: 可选的回调函数，格式为 async def callback(metrics_data: dict, worker_id: str)
                      如果不提供，数据将只通过事件系统处理
        """
        request_pubsub = None
        try:
            request_pubsub = self.redis.pubsub()

            # 订阅请求数据channel
            await request_pubsub.subscribe("aiotest:metrics")
            logger.info(
                "%s 开始从 Redis 监听请求指标", self.role)

            while True:  # 持续监听，由外部控制停止
                try:
                    # 获取请求数据消息
                    request_message = await request_pubsub.get_message(timeout=1.0)

                    # 处理请求数据
                    if request_message and request_message['type'] == 'message':
                        try:
                            message_data = json.loads(request_message['data'])

                            # 处理批量数据
                            batch = message_data.get('batch', [])
                            worker_id = message_data.get(
                                'worker_id', 'unknown')
                            chunk_index = message_data.get('chunk_index', 0)
                            total_chunks = message_data.get('total_chunks', 1)

                            # 记录分块信息（如果是分块传输）
                            if total_chunks > 1:
                                logger.debug(
                                    "处理指标分块 %d/%d，来自 %s",
                                    chunk_index + 1, total_chunks, worker_id)

                            # 遍历批量数据并调用回调
                            for metrics_data in batch:
                                if callback:
                                    await callback(metrics_data, worker_id)

                        except (json.JSONDecodeError, KeyError, Exception) as e:
                            if isinstance(e, (json.JSONDecodeError, KeyError)):
                                logger.warning(
                                    "从 Redis 解析请求指标失败: %s",
                                    str(e))
                            else:
                                logger.warning(
                                    "处理请求指标回调失败: %s",
                                    str(e))

                except asyncio.CancelledError:
                    # 任务被取消，记录日志并退出
                    logger.info("请求指标监听器任务已取消")
                    raise
                except Exception as e:
                    logger.warning("Redis消息处理错误: %s", str(e))
                    await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            # 任务被取消，记录日志并退出
            logger.info("请求指标监听器已停止")
            raise
        except Exception as e:
            logger.error("Redis请求指标监听器失败: %s", str(e))
        finally:
            # 清理pubsub连接
            if request_pubsub:
                try:
                    await request_pubsub.unsubscribe("aiotest:metrics")
                    await request_pubsub.close()
                except Exception as e:
                    logger.warning(
                        "清理请求指标 pubsub 时出错: %s",
                        str(e))
            logger.info("Redis请求指标监听器已停止")

    async def listen_commands(self, command_handler):
        """
        统一的命令监听器

        参数：
            command_handler: 命令处理函数，格式为 async def handler(data: dict, worker_id: str, command: str)
        """
        pubsub = None
        try:
            pubsub = self.redis.pubsub()
            await pubsub.subscribe(self.subscribe_channel)
            logger.info(
                "%s 开始在 %s 上监听命令", self.role, self.subscribe_channel)

            # 持续监听，直到收到quit命令或任务被取消
            while True:
                try:
                    # 获取消息，使用async for循环来监听，这样更可靠
                    async for message in pubsub.listen():
                        if message["type"] == "message":
                            try:
                                data = json.loads(message["data"])
                                command = data.get("command")
                                command_data = data.get("data")
                                worker_id = data.get("worker_id")

                                logger.info(
                                    "收到命令: %s, 数据: %s, worker_id: %s",
                                    command, command_data, worker_id)

                                # 只处理发给当前节点的命令（如果有worker_id过滤）
                                # Master节点接收所有Worker节点的命令，Worker节点只接收发给自己的命令
                                if self.role == "worker" and worker_id and hasattr(
                                        self, 'node_id') and worker_id != self.node_id:
                                    logger.info(
                                        "命令不是发给当前worker，跳过。worker_id: %s, self.node_id: %s",
                                        worker_id, self.node_id)
                                    continue

                                # 调用统一的命令处理器
                                logger.info("正在处理命令: %s", command)
                                await command_handler(command_data, worker_id, command)

                                # 如果是quit命令，退出循环
                                if command == "quit":
                                    logger.info(
                                        "收到退出命令，退出命令监听器")
                                    break

                            except json.JSONDecodeError:
                                logger.warning(
                                    "解析命令消息失败: %s", message)
                                continue
                            except Exception as e:
                                logger.error(
                                    "处理命令消息错误: %s", e)
                                continue
                        elif message["type"] == "subscribe":
                            # Redis 服务器确认订阅成功
                            logger.info(
                                "已订阅频道: %s",
                                message['channel'])
                        elif message["type"] == "unsubscribe":
                            # Redis 服务器确认取消订阅成功
                            logger.info(
                                "已取消订阅频道: %s",
                                message['channel'])
                            break

                except asyncio.CancelledError:
                    # 任务被取消，记录日志
                    logger.info("命令监听器任务已取消")
                    break
                except Exception as e:
                    logger.error("命令监听器错误: %s", str(e))
                    # 出错后，等待一段时间再继续监听
                    await asyncio.sleep(1.0)
                    continue

        except Exception as e:
            logger.error("命令监听器错误: %s", str(e))
        finally:
            if pubsub:
                try:
                    await pubsub.unsubscribe(self.subscribe_channel)
                    await pubsub.close()
                except Exception as e:
                    logger.warning(
                        "清理命令 pubsub 时出错: %s",
                        str(e))
            logger.info("命令监听器已停止")
