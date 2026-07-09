# encoding: utf-8
"""
Pytest 配置文件

包含共享的 fixtures 和配置，可以被所有测试文件使用
"""

import os

import pytest
from redis.asyncio import Redis

from aiotest import HTTPClient, HttpUser, LoadUserShape, User

# ============================================
# 常量配置（从环境变量读取，避免硬编码私密 IP）
# ============================================

# Redis 连接配置
REDIS_HOST = "172.16.40.25"
REDIS_PORT = 6379
REDIS_PASSWORD = "test123456"

# 测试服务器配置
TEST_HOST = "http://localhost:8080"
TEST_HTTPS_HOST = "https://localhost:8443"

# 默认超时配置
DEFAULT_TIMEOUT = 30
DEFAULT_WAIT_TIME = 0.1


# ============================================
# 测试用的类定义
# ============================================

class TestUser(User):
    """测试用的用户类"""

    async def test_task(self):
        pass


class TestLoadShape(LoadUserShape):
    """测试用的负载形状类"""

    def tick(self):
        return (10, 1.0)


# ============================================
# Fixtures
# ============================================

@pytest.fixture
async def redis_client():
    """
    创建 Redis 客户端 fixture

    用于需要 Redis 连接的测试用例

    Yields:
        Redis: 异步 Redis 客户端实例

    Example:
        async def test_something(self, redis_client):
            await redis_client.set("key", "value")
    """
    client = Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        decode_responses=True
    )
    yield client
    await client.close()


@pytest.fixture
def base_config():
    """
    基础配置 fixture

    用于需要基础配置的测试用例

    Returns:
        dict: 基础配置字典
    """
    return {
        "host": TEST_HOST,
        "timeout": DEFAULT_TIMEOUT
    }


@pytest.fixture
async def http_client():
    """
    创建 HTTPClient 实例 fixture

    用于需要 HTTPClient 的测试用例

    Yields:
        HTTPClient: 异步 HTTP 客户端实例

    Example:
        async def test_something(self, http_client):
            async with http_client.get("/") as response:
                assert response.status == 200
    """
    async with HTTPClient(base_url=TEST_HOST) as client:
        yield client


@pytest.fixture
async def https_client():
    """
    创建 HTTPS HTTPClient 实例 fixture

    用于需要 HTTPS 连接的测试用例

    Yields:
        HTTPClient: 异步 HTTPS 客户端实例
    """
    async with HTTPClient(base_url=TEST_HTTPS_HOST, verify_ssl=False) as client:
        yield client


@pytest.fixture
async def http_user():
    """
    创建并初始化 HttpUser 实例 fixture

    用于需要 HttpUser 的测试用例

    Yields:
        HttpUser: 异步 HttpUser 实例

    Example:
        async def test_something(self, http_user):
            async with http_user.client.get("/") as response:
                assert response.status == 200
    """
    user = HttpUser(host=TEST_HOST)
    await user._ensure_client_initialized()
    yield user
    await user.on_stop()


@pytest.fixture
def test_load_shape():
    """
    创建测试用的负载形状实例 fixture

    用于需要 LoadUserShape 的测试用例

    Returns:
        LoadUserShape: 负载形状实例

    Example:
        def test_something(self, test_load_shape):
            user_count, rate = test_load_shape.tick()
            assert user_count == 10
    """
    return TestLoadShape()


@pytest.fixture
async def preconfigured_http_client():
    """
    创建并初始化一个预配置的 HTTPClient 实例 fixture

    用于需要预配置 HTTPClient 的测试用例

    Yields:
        HTTPClient: 异步 HTTP 客户端实例

    Example:
        async def test_something(self, preconfigured_http_client):
            async with preconfigured_http_client.get("/") as response:
                assert response.status == 200
    """
    client = HTTPClient(base_url=TEST_HOST)
    await client.__aenter__()
    yield client
    if client._session is not None:
        await client.__aexit__(None, None, None)


@pytest.fixture
def mock_config():
    """
    创建测试用的配置类 fixture

    用于需要配置对象的测试用例

    Returns:
        MockConfig: 测试配置类实例

    Example:
        def test_something(self, mock_config):
            config = mock_config(prometheus_port=8000)
            # 使用配置
    """
    class MockConfig:
        def __init__(self, prometheus_port=8000,
                     metrics_collection_interval=5.0):
            self.prometheus_port = prometheus_port
            self.metrics_collection_interval = metrics_collection_interval
            self.metrics_batch_size = 100
            self.metrics_flush_interval = 1.0
            self.metrics_buffer_size = 10000
            self.loglevel = "INFO"
            self.logfile = None
            self.redis_path = "127.0.0.1"
            self.redis_port = 6379
            self.redis_password = "123456"
            self.master = False
            self.worker = False
            self.expect_workers = 1
            self.host = ""
            self.aiotestfile = "aiotestfile"
            self.show_users_weight = False
    return MockConfig


@pytest.fixture
def mock_redis_client():
    """
    创建测试用的 Redis 客户端模拟 fixture

    用于需要 Redis 客户端的测试用例

    Returns:
        MockRedisClient: 模拟的 Redis 客户端

    Example:
        def test_something(self, mock_redis_client):
            redis_client = mock_redis_client()
            # 使用 Redis 客户端
    """
    class MockRedisClient:
        async def publish(self, *args, **kwargs):
            pass

        async def subscribe(self, *args, **kwargs):
            class MockPubSub:
                async def get_message(self, *args, **kwargs):
                    return None

                async def listen(self, *args, **kwargs):
                    # 异步生成器，不产生任何消息
                    if False:
                        yield  # noqa: 保持生成器接口
            return MockPubSub()


        async def pubsub(self, *args, **kwargs):
            """返回一个模拟的PubSub对象，用于subscribe/get_message/listen"""
            class MockPubSub:
                async def subscribe(self, *args, **kwargs):
                    pass

                async def get_message(self, *args, **kwargs):
                    return None

                async def listen(self, *args, **kwargs):
                    # 异步生成器，不产生任何消息
                    if False:
                        yield  # noqa: 保持生成器接口
            return MockPubSub()

        async def scan(self, cursor=0, match=None, count=None):
            """返回 (cursor, keys) 元组，模拟无匹配key"""
            return (0, [])

        async def hgetall(self, key):
            """返回空的hash数据"""
            return {}

        async def time(self):
            """返回模拟的Redis服务器时间 (秒, 微秒)"""
            import time as _time
            t = _time.time()
            return (int(t), int((t - int(t)) * 1_000_000))

        async def hset(self, *args, **kwargs):
            pass

        async def set(self, *args, **kwargs):
            pass

        async def get(self, *args, **kwargs):
            return None

        async def close(self):
            pass
    return MockRedisClient
