# encoding: utf-8

"""
AioTest 秒杀场景测试示例

这个示例实现了"所有用户准备好后再执行压测"的场景，模拟秒杀场景：所有用户同时发起请求。

运行方式:
    # 请先使用 examples/prepare_user_data.py 准备好用户数据
    # 请先确保 Redis 服务已启动，并且配置信息正确

    # local模式
    py -m aiotest -f examples/seckill_scenario.py --loglevel DEBUG

    # 分布式模式
    # 启动 Master 节点
    py -m aiotest -f examples/seckill_scenario.py \
        --master --expect-workers 2 \
        --redis-path 172.16.40.25 --redis-port 6379 --redis-password test123456

    # 启动 Worker 节点（在两个不同的终端）
    py -m aiotest -f examples/seckill_scenario.py \
        --worker \
        --redis-path 172.16.40.25 --redis-port 6379 --redis-password test123456

功能说明:
    - 使用 Redis 存储用户信息
    - 多个 Worker 节点从 Redis 拉取用户进行测试
    - 使用信号量实现所有用户等待
    - 在 startup_completed 事件触发时释放信号量
    - 模拟秒杀场景：所有用户同时发起请求
"""

import asyncio
import json

from aiotest import (DistributedLock, HttpUser, LoadUserShape, RedisConnection,
                     logger, startup_completed)
from aiotest.cli import parse_options

# 获取命令行参数
options = parse_options()

# Redis 连接配置
REDIS_PATH = options.redis_path
REDIS_PORT = options.redis_port
REDIS_PASSWORD = options.redis_password

# 全局 Redis 连接
redis_client = None
redis_connection = None

# 信号量：用于控制所有用户等待
# 初始化时信号量为0，所有用户会被阻塞
users_ready_semaphore = asyncio.Semaphore(0)

# 标志：确保事件处理器只执行一次
_startup_completed_triggered = False


@startup_completed.handler()
async def on_startup_completed(**kwargs):
    """
    启动完成事件处理器

    当所有用户启动完成后，startup_completed 事件会被触发，
    此时释放信号量，允许所有用户开始执行任务。
    """
    global _startup_completed_triggered

    # 确保只执行一次
    if _startup_completed_triggered:
        return

    _startup_completed_triggered = True
    logger.info("所有用户已准备就绪，释放信号量，开始压测！")
    users_ready_semaphore.release()


async def initialize_redis():
    """初始化 Redis 连接"""
    global redis_client, redis_connection
    if redis_client is None:
        if redis_connection is None:
            redis_connection = RedisConnection()
        redis_client = await redis_connection.get_client(
            path=REDIS_PATH,
            port=REDIS_PORT,
            password=REDIS_PASSWORD
        )
        logger.info("Redis connection initialized")
    return redis_client


class SeckillUser(HttpUser):
    """
    秒杀用户类，从 Redis 拉取用户信息进行测试

    这个示例展示了如何在分布式模式下实现秒杀场景：
    1. 从 Redis 拉取用户信息
    2. 所有用户等待信号量
    3. 当 startup_completed 事件触发时，信号量被释放
    4. 所有用户同时开始执行任务（模拟秒杀）
    """

    # 目标服务器地址（使用 httpbin.org 作为测试目标）
    host = "https://httpbin.org"

    # 请求间隔时间（2-3秒之间随机），避免httpbin服务崩溃
    wait_time = (2, 3)

    # Redis 键定义
    available_users_key = "aiotest:available_users"  # 可用的用户卡号集合
    user_details_key = "aiotest:user_details"  # 用户详细信息 Hash

    async def on_start(self):
        """
        用户启动时的初始化方法

        从 Redis 拉取用户信息，然后等待信号量
        """
        # 调用父类方法初始化 HTTP 客户端
        await super().on_start()

        # 初始化 Redis 连接
        self.redis = await initialize_redis()

        # 从 Redis 拉取用户卡号
        self.card_number = await self.redis.spop(self.available_users_key)
        if not self.card_number:
            logger.error("Redis 中没有可用的用户卡号")
            return

        logger.info(f"获取到用户卡号: {self.card_number}")

        # 初始化必要的属性
        self.user_info = None
        self.headers = None

        # 使用分布式锁确保并发安全（确保多个 Worker 节点不会同时操作同一个用户）
        lock_key = f"lock:{self.card_number}"
        async with await DistributedLock.with_lock(self.redis, lock_key, timeout=10) as lock:
            if lock.locked:
                # 获取用户基本信息
                user_data = await self.redis.hget(self.user_details_key, self.card_number)
                if not user_data:
                    logger.error(f"用户 {self.card_number} 不存在")
                    return

                # 处理用户数据
                self.user_info = json.loads(user_data)
                # 根据实际存储的字段构建 headers
                self.headers = {
                    "Authorization": f'bearer {self.user_info["token"]}',
                    "User-ID": self.user_info["id"],
                    "Card-Number": self.card_number
                }

                logger.info(f"用户 {self.card_number} 登录成功")

        if not self.headers:
            logger.error("缺少认证信息，无法继续执行")
            return

        # 关键：等待信号量，直到所有用户准备就绪
        logger.info(f"用户 {self.card_number} 已准备好，等待信号量...")
        await users_ready_semaphore.acquire()
        logger.info(f"用户 {self.card_number} 收到信号量，开始执行任务！")

    async def on_stop(self):
        """
        用户停止时的清理方法

        关闭 Redis 连接，将用户卡号放回 Redis
        """
        # 将卡号放回 Redis，以便下次测试使用
        if hasattr(self, 'card_number') and self.card_number:
            try:
                await self.redis.sadd(self.available_users_key, self.card_number)
                logger.info(f"用户卡号 {self.card_number} 已放回 Redis")
            except Exception as e:
                logger.error(f"放回用户卡号失败: {str(e)}")

        # 不要在这里关闭 Redis 连接，因为每个用户实例都有自己的 Redis 连接池
        # 测试退出时，会自动关闭所有连接池

        # 调用父类方法关闭 HTTP 客户端
        await super().on_stop()

    async def test_seckill(self):
        """
        秒杀请求测试

        模拟秒杀场景，所有用户同时发起请求
        """
        if not self.headers or not self.user_info:
            logger.error("缺少认证信息，跳过测试")
            return

        # 模拟秒杀请求
        payload = {
            "user_id": self.user_info["id"],
            "username": self.user_info["username"],
            "action": "seckill",
            "product_id": "PROD-001",
            "timestamp": asyncio.get_event_loop().time()
        }

        async with self.client.post(endpoint="/post", json=payload, headers=self.headers, name="Seckill Request") as resp:
            data = await resp.json()
            assert resp.status == 200
            logger.info(f"用户 {self.card_number} 秒杀请求成功")

    async def test_authenticated_request(self):
        """
        使用认证信息的请求测试
        """
        if not self.headers:
            logger.error("缺少认证信息，跳过测试")
            return

        # 使用在 on_start 中获取的认证信息
        async with self.client.get(endpoint="/headers", headers=self.headers, name="Authenticated Request") as resp:
            data = await resp.json()
            assert resp.status == 200
            # 验证认证信息被正确发送
            assert "headers" in data
            sent_headers = data["headers"]
            assert "Authorization" in sent_headers or "authorization" in sent_headers
            logger.info(f"用户 {self.card_number} 认证请求成功")


class SeckillLoadShape(LoadUserShape):
    """
    秒杀场景负载形状定义

    这个负载形状设计用于秒杀场景，
    快速启动所有用户，然后同时开始执行任务。
    """

    # 定义负载阶段
    # 快速启动所有用户，适合秒杀场景
    stages = [
        {"duration": 60, "user_count": 20, "rate": 2},
        {"duration": 90, "user_count": 4, "rate": 2},
    ]

    def tick(self):
        """
        计算当前应该使用的用户数和生成速率

        返回: (user_count, rate) 或 None
        """
        run_time = self.get_run_time()

        for stage in self.stages:
            if run_time < stage["duration"]:
                return (stage["user_count"], stage["rate"])

        return None
