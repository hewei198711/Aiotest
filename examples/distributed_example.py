# encoding: utf-8

"""
AioTest 分布式测试示例文件

这是一个分布式负载测试的示例，展示如何使用 Redis 存储用户信息，
并让多个 Worker 节点从 Redis 拉取用户进行登录测试。

运行方式:
    # 请先使用examples/prepare_user_data.py 准备好用户数据（默认会导入examples/user_data.csv 文件中的用户数据）
    # 请先确保 Redis 服务已启动，并且配置信息正确

    # 启动 Master 节点
    aiotest -f examples/distributed_example.py \
        --master --expect-workers 2 \
        --redis-path 172.16.40.24 --redis-port 6379 --redis-password test123456

    # 启动 Worker 节点（在两个不同的终端）
    aiotest -f examples/distributed_example.py \
        --worker \
        --redis-path 172.16.40.24 --redis-port 6379 --redis-password test123456

使用 DEBUG 日志级别查看详细信息:
    aiotest -f examples/distributed_example.py --loglevel DEBUG

功能说明:
    - 使用 Redis 存储用户信息
    - 多个 Worker 节点从 Redis 拉取用户进行登录测试
    - 支持分布式负载测试
    - 模拟真实的用户登录流程
"""

import json

from aiotest import (DistributedLock, HttpUser, LoadUserShape, RedisConnection,
                     logger)
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


class TestUser(HttpUser):
    """
    用户类，从 Redis 拉取用户信息进行登录测试

    这个示例展示了如何在分布式模式下：
    1. 从 Redis 拉取用户信息
    2. 使用用户信息进行登录测试
    3. 处理并发访问 Redis 的情况
    """

    # 目标服务器地址（使用 httpbin.org 作为测试目标）
    host = "https://httpbin.org"

    # 请求间隔时间（1-2秒之间随机）
    wait_time = (1, 2)

    # Redis 键定义
    available_users_key = "aiotest:available_users"  # 可用的用户卡号集合
    user_details_key = "aiotest:user_details"  # 用户详细信息 Hash

    async def on_start(self):
        """
        用户启动时的初始化方法

        从 Redis 拉取用户信息，用于后续的登录测试
        """
        # 调用父类方法初始化 HTTP 客户端
        await super().on_start()

        # 初始化必要的属性
        self.card_number = None
        self.user_info = None
        self.headers = None

        # 初始化 Redis 连接
        self.redis = await initialize_redis()

        # 从 Redis 拉取用户卡号
        self.card_number = await self.redis.spop(self.available_users_key)
        if not self.card_number:
            logger.error("Redis 中没有可用的用户卡号")
            return

        logger.info(f"获取到用户卡号: {self.card_number}")

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

    async def on_stop(self):
        """
        用户停止时的清理方法

        关闭 Redis 连接
        """
        # 将卡号放回 Redis，以便下次测试使用
        if hasattr(self, 'card_number') and self.card_number and hasattr(self, 'redis') and self.redis:
            try:
                await self.redis.sadd(self.available_users_key, self.card_number)
                logger.info(f"用户卡号 {self.card_number} 已放回 Redis")
            except Exception as e:
                logger.error(f"放回用户卡号失败: {str(e)}")
        
        # 不要在这里关闭 Redis 连接，因为每个用户实例都有自己的 Redis 连接池
        # 测试退出时，会自动关闭所有连接池

        # 调用父类方法关闭 HTTP 客户端
        await super().on_stop()

    async def test_authenticated_request(self):
        """
        使用认证信息的请求测试

        演示如何使用从 Redis 获取的用户信息进行认证请求
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

    async def test_get_ip(self):
        """
        获取客户端 IP 信息

        测试基本的 GET 请求
        """
        if not self.headers:
            logger.error("缺少认证信息，跳过测试")
            return

        async with self.client.get(endpoint="/ip", headers=self.headers, name="Get IP") as resp:
            data = await resp.json()
            assert resp.status == 200
            assert "origin" in data
            logger.info(f"用户 {self.card_number} 获取 IP 成功")

    async def test_post_user_info(self):
        """
        发送用户信息的 POST 请求

        测试使用用户信息发送 POST 请求
        """
        if not self.headers or not self.user_info:
            logger.error("缺少认证信息，跳过测试")
            return

        # 发送用户信息
        payload = {
            "id": self.user_info["id"],
            "cardNumber": self.card_number,
            "username": self.user_info["username"]
        }

        async with self.client.post(endpoint="/post", json=payload, headers=self.headers, name="Post User Info") as resp:
            data = await resp.json()
            assert resp.status == 200
            assert "json" in data
            assert data["json"]["id"] == self.user_info["id"]
            logger.info(f"用户 {self.card_number} 发送用户信息成功")


class TestLoadShape(LoadUserShape):
    """
    分布式测试负载形状定义

    这个负载形状设计用于分布式测试场景，
    适合 2 个 Worker 节点的情况。
    """

    # 定义负载阶段
    # 总用户数 20，每个 Worker 节点处理 10 个用户
    stages = [
        {"duration": 60, "user_count": 20, "rate": 2},    # 0-60秒：20个用户，每秒启动2个
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
