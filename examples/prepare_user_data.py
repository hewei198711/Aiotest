# encoding: utf-8

"""
用户数据准备工具（正常测试要求先提前准备好用户数据，例如用户提前登录，获取后续测试所需要的token）

这个工具用于从 CSV 文件导入用户数据，模拟登录过程，并将登录后的信息写入 Redis，
以便与 distributed_example.py 配合使用。

运行方式:
    py -m examples.prepare_user_data

功能说明:
    - 从 CSV 文件读取用户数据
    - 调用 httpbin 接口模拟登录，获取 token
    - 批量处理大批量用户（支持 2 万个用户）
    - 将登录后的用户信息写入 Redis
    - 与 distributed_example.py 使用相同的 Redis 键结构

Redis 键结构:
    - aiotest:available_users: 可用的用户卡号集合
    - aiotest:user_details: 用户详细信息 Hash
"""

import asyncio
import csv
import json
import os
import random
import string
import time

from aiotest import HTTPClient, RedisConnection, logger

# Redis 连接配置
REDIS_PATH = "172.16.40.25"
REDIS_PORT = 6379
REDIS_PASSWORD = "test123456"

# CSV 文件路径，使用相对于脚本所在目录的路径
CSV_FILE_PATH = os.path.join(os.path.dirname(__file__), "userinfo.csv")

# Redis 键定义
AVAILABLE_USERS_KEY = "aiotest:available_users"  # 可用的用户卡号集合
USER_DETAILS_KEY = "aiotest:user_details"  # 用户详细信息 Hash

# 批量处理配置
BATCH_SIZE = 10  # 每批处理的用户数量
WORKER_COUNT = 2  # 并发协程数


class UserDataPreparer:
    """用户数据准备类"""

    def __init__(self, redis, csv_path=CSV_FILE_PATH):
        self.redis = redis
        self.csv_path = csv_path
        self._client = None

    @property
    def client(self):
        """获取 HTTP 客户端"""
        if self._client is None:
            raise RuntimeError(
                "HTTP Client not initialized. Call on_start() first.")
        return self._client

    async def on_start(self):
        """初始化 HTTP 客户端"""
        if self._client is None:
            self._client = await HTTPClient(
                base_url="https://httpbin.org",
                timeout=30,
                max_retries=3,
            ).__aenter__()

    async def on_stop(self):
        """关闭 HTTP 客户端"""
        if self._client:
            try:
                await self._client.__aexit__(None, None, None)
                self._client = None
            except Exception as e:
                logger.error(f"关闭 HTTP 客户端失败: {str(e)}")

    async def clear_existing_data(self):
        """清除 Redis 中现有的用户数据"""
        try:
            async with self.redis.pipeline() as pipe:
                pipe.delete(AVAILABLE_USERS_KEY)
                pipe.delete(USER_DETAILS_KEY)
                await pipe.execute()
            logger.info("已清除 Redis 中现有的用户数据")
        except Exception as e:
            logger.error(f"清除 Redis 数据失败: {str(e)}")
            raise

    async def import_from_csv(self):
        """从 CSV 文件导入用户数据到 Redis"""
        try:
            # 批量处理用户数据
            count = 0
            start_time = time.time()
            batch = []
            total_users = 0

            # 逐行读取 CSV 文件，避免一次性加载所有数据
            with open(self.csv_path, mode='r', encoding='utf-8') as file:
                reader = csv.reader(file)
                header = next(reader)  # 读取标题行
                logger.info(f"CSV 文件标题: {header}")

                # 先计算总用户数
                for row in reader:
                    if row:
                        total_users += 1

                # 重置文件指针到数据开始位置
                file.seek(0)
                next(reader)  # 跳过标题行

                logger.info(f"从 CSV 文件读取到 {total_users} 个用户数据")

                # 计算总批次数(向上取整)
                # 20 个用户，每批 10 个: (20 + 10 - 1) // 10 = 29 // 10 --> 2
                # 25 个用户，每批 10 个: (25 + 10 - 1) // 10 = 34 // 10 --> 3
                # 30 个用户，每批 10 个: (30 + 10 - 1) // 10 = 39 // 10 --> 3
                total_batches = (total_users + BATCH_SIZE - 1) // BATCH_SIZE
                logger.info(f"共分成 {total_batches} 个批次，每批 {BATCH_SIZE} 个用户")

                batch_idx = 0
                for row in reader:
                    if not row:
                        continue
                    # 解析 CSV 行数据
                    # 假设 CSV 文件格式: id,phone,user,type(根据实际情况调整)
                    user_id, phone, user, user_type = row
                    batch.append((user, user_id, phone, user_type))

                    # 当批次达到指定大小时，处理该批次
                    if len(batch) >= BATCH_SIZE:
                        batch_idx += 1
                        await self._process_batch(batch, batch_idx, total_batches)
                        count += len(batch)
                        batch = []

            # 处理剩余的批次
            if batch:
                batch_idx += 1
                await self._process_batch(batch, batch_idx, total_batches)
                count += len(batch)

            total_duration = time.time() - start_time
            logger.info(f"成功处理 {count} 个用户数据，耗时: {total_duration:.2f} 秒")
            return count
        except Exception as e:
            logger.error(f"导入用户数据失败: {str(e)}")
            raise

    async def _process_batch(self, batch, batch_idx, total_batches):
        """处理单个批次的用户数据"""
        batch_start_time = time.time()

        # 进一步将批次分成更小的组，以便并发处理
        # range(0, len(batch), WORKER_COUNT)：生成一个从 0 开始，步长为 WORKER_COUNT 的序列
        # batch[i:i+WORKER_COUNT] : 从 batch 中切片出从索引 i 到 i+WORKER_COUNT 的子列表
        # 当 len(batch)=10 ， WORKER_COUNT=2 时，生成 [0, 2, 4, 6, 8]
        # batch[0:2] → 第 1-2 个用户
        # batch[2:4] → 第 3-4 个用户
        # batch[4:6] → 第 5-6 个用户
        # batch[6:8] → 第 7-8 个用户
        # batch[8:10] → 第 9-10 个用户
        sub_batches = [batch[i:i + WORKER_COUNT]
                       for i in range(0, len(batch), WORKER_COUNT)]

        for sub_batch in sub_batches:
            sub_tasks = [
                self._process_user(user, user_id, phone, user_type)
                for user, user_id, phone, user_type in sub_batch
            ]
            results = await asyncio.gather(*sub_tasks, return_exceptions=True)

            # 处理结果
            for result in results:
                if isinstance(result, tuple):
                    user, user_info = result
                    await self._save_user(user, user_info)
                else:
                    logger.error(f"处理用户失败: {str(result)}")

        batch_duration = time.time() - batch_start_time
        progress = batch_idx / total_batches * 100
        logger.info(
            f"批次 {batch_idx}/{total_batches} 处理完成，耗时: {
                batch_duration:.2f} 秒，进度: {
                progress:.1f}%")

    async def _process_user(self, user, user_id, phone, user_type):
        """处理单个用户，模拟登录并获取 token"""
        try:
            # 调用 httpbin 接口模拟登录，获取 token
            user_info = await self._simulate_login(user, user_id, phone, user_type)
            return (user, user_info)
        except Exception as e:
            logger.error(f"处理用户 {user} 失败: {str(e)}")
            raise

    async def _simulate_login(self, user, user_id, phone, user_type):
        """模拟登录过程，调用 httpbin 接口获取 token"""
        try:
            # 调用 httpbin 的 post 接口模拟登录
            login_data = {
                "username": user,
                "password": "123456",
                "user_id": user_id,
                "phone": phone
            }

            async with self.client.post("/post", json=login_data) as resp:
                if resp.status != 200:
                    raise Exception(f"登录失败，状态码: {resp.status}")

                # 从响应中提取数据，模拟 token
                response_data = await resp.json()
                # 生成基于响应数据的 token
                token = f"token_{user}_{
                    ''.join(
                        random.sample(
                            string.ascii_letters +
                            string.digits,
                            16))}"

            # 构建用户信息
            user_info = {
                "id": user_id,
                "user": user,
                "phone": phone,
                "type": user_type,
                "token": token,
                "username": f"user_{user}",
                "password": "123456"
            }

            return user_info
        except Exception as e:
            logger.error(f"模拟登录失败 {user}: {str(e)}")
            # 即使登录失败，也生成一个 token 以便测试
            token = f"token_{user}_{
                ''.join(
                    random.sample(
                        string.ascii_letters +
                        string.digits,
                        16))}"
            return {
                "id": user_id,
                "user": user,
                "phone": phone,
                "type": user_type,
                "token": token,
                "username": f"user_{user}",
                "password": "123456"
            }

    async def _save_user(self, user, user_info):
        """保存单个用户数据到 Redis"""
        try:
            async with self.redis.pipeline(transaction=True) as pipe:
                pipe.sadd(AVAILABLE_USERS_KEY, user)
                pipe.hset(USER_DETAILS_KEY, user, json.dumps(user_info))
                result = await pipe.execute()
        except Exception as e:
            logger.error(f"保存用户数据失败 {user}: {str(e)}")
            raise

    async def get_stats(self):
        """获取 Redis 中的用户数据统计信息"""
        try:
            async with self.redis.pipeline() as pipe:
                pipe.scard(AVAILABLE_USERS_KEY)
                pipe.hlen(USER_DETAILS_KEY)
                available_users_count, user_details_count = await pipe.execute()

            return {
                "available_users_count": available_users_count,
                "user_details_count": user_details_count
            }
        except Exception as e:
            logger.error(f"获取统计信息失败: {str(e)}")
            return {}


async def main():
    """主函数"""
    preparer = None
    redis_connection = None

    try:
        logger.info("=== 用户数据准备开始 ===")

        # 连接 Redis
        redis_connection = RedisConnection()
        redis = await redis_connection.get_client(
            path=REDIS_PATH,
            port=REDIS_PORT,
            password=REDIS_PASSWORD
        )

        # 创建用户数据准备器
        preparer = UserDataPreparer(redis, csv_path=CSV_FILE_PATH)

        # 初始化 HTTP 客户端
        await preparer.on_start()

        # 清除现有数据
        await preparer.clear_existing_data()

        # 开始导入
        start_time = time.time()
        count = await preparer.import_from_csv()
        duration = time.time() - start_time

        # 获取统计信息
        stats = await preparer.get_stats()

        # 打印结果
        logger.info("\n=== 用户数据准备完成 ===")
        logger.info(f"耗时: {duration:.2f} 秒")
        logger.info(f"处理用户数量: {count}")
        logger.info(
            f"Redis 中 available_users 数量: {
                stats['available_users_count']}")
        logger.info(f"Redis 中 user_details 数量: {stats['user_details_count']}")
        logger.info("\n数据已准备就绪，可以开始运行 distributed_example.py 进行分布式测试")

    except Exception as e:
        logger.error(f"主进程错误: {str(e)}")
    finally:
        # 关闭 HTTP 客户端
        if preparer:
            await preparer.on_stop()

        # 关闭 Redis 连接
        if redis_connection:
            await redis_connection.close()

        logger.info("=== 用户数据准备结束 ===")


if __name__ == "__main__":
    # 设置日志级别
    logger.setLevel("DEBUG")
    # 运行主函数
    asyncio.run(main())
