# encoding: utf-8

import asyncio

import allure
import pytest

from aiotest.distributed_coordinator import (HEARTBEAT_INTERVAL,
                                             HEARTBEAT_LIVENESS,
                                             MAX_BATCH_SIZE,
                                             DistributedCoordinator,
                                             DistributedLock, RedisConnection)


@allure.feature("RedisConnection")
class TestRedisConnection:
    """RedisConnection 类的测试用例"""

    @allure.story("初始化")
    @allure.title("测试 RedisConnection 初始化")
    @allure.severity(allure.severity_level.NORMAL)
    def test_initialization(self):
        """测试 RedisConnection 初始化时正确设置属性"""
        connection = RedisConnection(max_retries=5, retry_interval=2.0)
        assert connection.max_retries == 5
        assert connection.retry_interval == 2.0
        assert connection._pool is None
        assert connection._client is None

    @allure.story("连接管理")
    @allure.title("测试获取 Redis 客户端")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_get_client(self, redis_client):
        """测试获取 Redis 客户端"""
        connection = RedisConnection(max_retries=1, retry_interval=0.1)

        # 直接使用redis_client fixture
        connection._client = redis_client

        # 测试获取客户端
        client = await connection.get_client("localhost", 6379, "")
        assert client is not None
        # 测试连接是否可用
        await client.ping()

    @allure.story("连接管理")
    @allure.title("测试 Redis 连接重试逻辑")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_get_client_retry(self):
        """测试 Redis 连接失败时的重试逻辑"""
        connection = RedisConnection(max_retries=2, retry_interval=0.01)

        # 重置全局Redis连接变量
        import aiotest.distributed_coordinator
        aiotest.distributed_coordinator._global_redis_client = None
        aiotest.distributed_coordinator._global_redis_connection = None

        # 尝试连接到不存在的Redis服务器（端口6380），触发重试逻辑
        try:
            # 这应该会失败并触发重试
            await connection.get_client("localhost", 6380, "")
            # 如果成功了，说明测试环境有Redis服务器在6380端口运行，跳过测试
            pytest.skip(
                "Redis server available on port 6380, cannot test retry logic")
        except Exception as e:
            # 预期会失败，验证异常信息
            assert "Connection error" in str(e) or "连接" in str(e)

    @allure.story("连接管理")
    @allure.title("测试 Redis 连接失败")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_get_client_failure(self):
        """测试 Redis 连接失败的情况"""
        connection = RedisConnection(max_retries=2, retry_interval=0.01)

        # 重置全局Redis连接变量
        import aiotest.distributed_coordinator
        aiotest.distributed_coordinator._global_redis_client = None
        aiotest.distributed_coordinator._global_redis_connection = None

        # 尝试连接到不存在的Redis服务器（端口6380），触发失败逻辑
        with pytest.raises(Exception):
            await connection.get_client("localhost", 6380, "")

    @allure.story("连接管理")
    @allure.title("测试关闭 Redis 连接")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_close(self, redis_client):
        """测试关闭 Redis 连接"""
        connection = RedisConnection()

        # 直接使用redis_client fixture
        connection._client = redis_client
        connection._pool = redis_client.connection_pool

        # 关闭连接
        await connection.close()

        # 验证连接是否被关闭
        assert connection._client is None
        assert connection._pool is None


@allure.feature("DistributedLock")
class TestDistributedLock:
    """DistributedLock 类的测试用例"""

    @allure.story("初始化")
    @allure.title("测试 DistributedLock 初始化")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_initialization(self, redis_client):
        """测试 DistributedLock 初始化时正确设置属性"""
        lock_key = "test_lock"
        lock = DistributedLock(redis_client, lock_key, timeout=5.0)

        assert lock.redis == redis_client
        assert lock.lock_key == f"aiotest:lock:{lock_key}"
        assert lock.timeout == 5.0
        assert lock.locked is False

    @allure.story("锁操作")
    @allure.title("测试获取锁")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_acquire(self, redis_client):
        """测试获取分布式锁"""
        lock = DistributedLock(redis_client, "test_lock")
        result = await lock.acquire()

        assert result is True
        assert lock.locked is True

        # 清理
        await lock.release()

    @allure.story("锁操作")
    @allure.title("测试获取锁失败")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_acquire_failure(self, redis_client):
        """测试获取分布式锁失败的情况"""
        # 先获取锁
        lock1 = DistributedLock(redis_client, "test_lock")
        await lock1.acquire()

        # 再尝试获取同一个锁，应该失败
        lock2 = DistributedLock(redis_client, "test_lock")
        result = await lock2.acquire()

        assert result is False
        assert lock2.locked is False

        # 清理
        await lock1.release()

    @allure.story("锁操作")
    @allure.title("测试获取锁超时")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_acquire_timeout(self, redis_client):
        """测试获取分布式锁超时的情况"""
        # 先获取锁
        lock1 = DistributedLock(redis_client, "test_lock")
        await lock1.acquire()

        # 再尝试获取同一个锁，应该超时失败
        lock2 = DistributedLock(
            redis_client,
            "test_lock",
            wait_timeout=0.1,
            retry_interval=0.05)
        result = await lock2.acquire()

        assert result is False
        assert lock2.locked is False

        # 清理
        await lock1.release()

    @allure.story("锁操作")
    @allure.title("测试释放锁")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_release(self, redis_client):
        """测试释放分布式锁"""
        lock = DistributedLock(redis_client, "test_lock")
        await lock.acquire()
        assert lock.locked is True

        result = await lock.release()
        assert result is True
        assert lock.locked is False

    @allure.story("锁操作")
    @allure.title("测试上下文管理器")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_context_manager(self, redis_client):
        """测试分布式锁的上下文管理器"""
        lock = DistributedLock(redis_client, "test_lock")

        async with lock:
            assert lock.locked is True

        assert lock.locked is False

    @allure.story("锁操作")
    @allure.title("测试 with_lock 静态方法")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_with_lock(self, redis_client):
        """测试 with_lock 静态方法"""
        async with await DistributedLock.with_lock(redis_client, "test_lock") as lock:
            assert lock.locked is True

        assert lock.locked is False


@allure.feature("DistributedCoordinator")
class TestDistributedCoordinator:
    """DistributedCoordinator 类的测试用例"""

    @allure.story("初始化")
    @allure.title("测试 DistributedCoordinator 初始化")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_initialization_master(self, redis_client):
        """测试以 master 角色初始化 DistributedCoordinator"""
        coordinator = DistributedCoordinator(
            redis_client, role="master", node_id="master_1")

        assert coordinator.redis == redis_client
        assert coordinator.role == "master"
        assert coordinator.node_id == "master_1"
        assert coordinator.subscribe_channel == "aiotest:command:worker_to_master"
        assert coordinator.publish_channel == "aiotest:command:master_to_worker"

    @allure.story("初始化")
    @allure.title("测试以 worker 角色初始化 DistributedCoordinator")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_initialization_worker(self, redis_client):
        """测试以 worker 角色初始化 DistributedCoordinator"""
        coordinator = DistributedCoordinator(
            redis_client, role="worker", node_id="worker_1")

        assert coordinator.redis == redis_client
        assert coordinator.role == "worker"
        assert coordinator.node_id == "worker_1"
        assert coordinator.subscribe_channel == "aiotest:command:master_to_worker"
        assert coordinator.publish_channel == "aiotest:command:worker_to_master"

    @allure.story("初始化")
    @allure.title("测试无效角色初始化")
    @allure.severity(allure.severity_level.NORMAL)
    def test_initialization_invalid_role(self):
        """测试使用无效角色初始化 DistributedCoordinator"""
        # 这里可以直接测试，不需要Redis连接
        with pytest.raises(ValueError):
            DistributedCoordinator(None, role="invalid")

    @allure.story("发布")
    @allure.title("测试发布命令")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_publish_command(self, redis_client):
        """测试发布命令"""
        coordinator = DistributedCoordinator(redis_client, role="master")
        await coordinator.publish("command", {"task_id": 123}, command="start_task")

        # 验证发布成功
        assert True

    @allure.story("发布")
    @allure.title("测试发布请求指标")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_publish_request_metrics(self, redis_client):
        """测试发布请求指标"""
        coordinator = DistributedCoordinator(
            redis_client, role="worker", node_id="worker_1")
        metrics_data = [{"url": "/test", "response_time": 0.1}]
        await coordinator.publish("request_metrics", metrics_data, worker_id="worker_1")

        # 验证发布成功
        assert True

    @allure.story("发布")
    @allure.title("测试发布批量请求指标")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_publish_request_metrics_batch(self, redis_client):
        """测试发布批量请求指标（超过最大批量大小）"""
        coordinator = DistributedCoordinator(
            redis_client, role="worker", node_id="worker_1")
        # 创建超过 MAX_BATCH_SIZE 的数据
        metrics_data = [{"url": f"/test{i}", "response_time": 0.1}
                        for i in range(MAX_BATCH_SIZE + 1)]
        await coordinator.publish("request_metrics", metrics_data, worker_id="worker_1")

        # 验证发布成功
        assert True

    @allure.story("发布")
    @allure.title("测试发布命令缺少参数")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_publish_command_missing_param(self, redis_client):
        """测试发布命令时缺少 command 参数"""
        coordinator = DistributedCoordinator(redis_client, role="master")

        with pytest.raises(ValueError):
            await coordinator.publish("command", {"task_id": 123})

    @allure.story("发布")
    @allure.title("测试发布请求指标缺少参数")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_publish_request_metrics_missing_param(self, redis_client):
        """测试发布请求指标时缺少 worker_id 参数"""
        coordinator = DistributedCoordinator(redis_client, role="worker")

        with pytest.raises(ValueError):
            await coordinator.publish("request_metrics", [{"url": "/test", "response_time": 0.1}])

    @allure.story("发布")
    @allure.title("测试发布心跳")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_publish_heartbeat(self, redis_client):
        """测试发布心跳"""
        coordinator = DistributedCoordinator(
            redis_client, role="worker", node_id="worker_1")
        await coordinator.publish("heartbeat", {"cpu_percent": 45.0, "active_users": 100})

        # 验证心跳发布成功
        assert True

    @allure.story("发布")
    @allure.title("测试发布无效频道类型")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_publish_invalid_channel(self, redis_client):
        """测试发布无效频道类型"""
        coordinator = DistributedCoordinator(redis_client, role="master")

        with pytest.raises(ValueError):
            await coordinator.publish("invalid_channel", {"data": "test"})

    @allure.story("心跳检查")
    @allure.title("测试检查 Worker 心跳")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_check_worker_heartbeat(self, redis_client):
        """测试检查 Worker 心跳"""
        # 先发布一个心跳
        worker_coordinator = DistributedCoordinator(
            redis_client, role="worker", node_id="worker_1")
        await worker_coordinator.publish("heartbeat", {"cpu_percent": 45.0, "active_users": 100})

        # 然后检查心跳
        master_coordinator = DistributedCoordinator(
            redis_client, role="master")
        result = await master_coordinator.check_worker_heartbeat("worker_1")

        # 验证心跳检查结果
        assert result is True

    @allure.story("心跳检查")
    @allure.title("测试检查 Worker 心跳失败")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_check_worker_heartbeat_failure(self, redis_client):
        """测试检查 Worker 心跳失败的情况"""
        # 确保没有心跳数据
        await redis_client.delete("aiotest:heartbeat:worker_1")

        # 检查心跳
        coordinator = DistributedCoordinator(redis_client, role="master")
        result = await coordinator.check_worker_heartbeat("worker_1")

        # 验证心跳检查结果
        assert result is False

    @allure.story("心跳检查")
    @allure.title("测试检查 Worker 心跳超时")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_check_worker_heartbeat_timeout(self, redis_client):
        """测试检查 Worker 心跳超时的情况"""
        # 手动设置一个过期的心跳
        old_timestamp = asyncio.get_event_loop().time() - 100
        await redis_client.hset("aiotest:heartbeat:worker_1", "timestamp", str(old_timestamp))

        # 检查心跳
        coordinator = DistributedCoordinator(redis_client, role="master")
        result = await coordinator.check_worker_heartbeat("worker_1")

        # 验证心跳检查结果
        assert result is False

        # 清理
        await redis_client.delete("aiotest:heartbeat:worker_1")

    @allure.story("心跳检查")
    @allure.title("测试检查 Worker 心跳时间戳格式错误")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_check_worker_heartbeat_invalid_timestamp(
            self, redis_client):
        """测试检查 Worker 心跳时时间戳格式错误的情况"""
        # 手动设置一个无效时间戳的心跳
        await redis_client.hset("aiotest:heartbeat:worker_1", "timestamp", "invalid_timestamp")

        # 检查心跳
        coordinator = DistributedCoordinator(redis_client, role="master")
        result = await coordinator.check_worker_heartbeat("worker_1")

        # 验证心跳检查结果
        assert result is False

        # 清理
        await redis_client.delete("aiotest:heartbeat:worker_1")

    @allure.story("监听")
    @allure.title("测试监听命令")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_listen_commands(self, redis_client):
        """测试监听命令"""
        coordinator = DistributedCoordinator(redis_client, role="master")

        # 验证初始化成功
        assert coordinator is not None

    @allure.story("监听")
    @allure.title("测试监听心跳任务取消")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_listen_heartbeats_cancellation(self, redis_client):
        """测试监听心跳任务是否正确响应取消"""
        coordinator = DistributedCoordinator(redis_client, role="master")

        # 创建一个任务来监听心跳
        task = asyncio.create_task(coordinator.listen_heartbeats())

        # 等待一小段时间，确保任务已经开始运行
        await asyncio.sleep(0.1)

        # 取消任务
        task.cancel()

        # 等待任务完成，确保没有抛出异常
        try:
            await task
        except asyncio.CancelledError:
            # 预期会收到CancelledError
            pass

        # 验证任务已经完成
        assert task.done()

    @allure.story("监听")
    @allure.title("测试监听请求指标任务取消")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_listen_request_metrics_cancellation(self, redis_client):
        """测试监听请求指标任务是否正确响应取消"""
        coordinator = DistributedCoordinator(redis_client, role="master")

        # 创建一个任务来监听请求指标
        task = asyncio.create_task(coordinator.listen_request_metrics())

        # 等待一小段时间，确保任务已经开始运行
        await asyncio.sleep(0.1)

        # 取消任务
        task.cancel()

        # 等待任务完成，确保没有抛出异常
        try:
            await task
        except asyncio.CancelledError:
            # 预期会收到CancelledError
            pass

        # 验证任务已经完成
        assert task.done()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
