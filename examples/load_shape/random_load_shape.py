# encoding: utf-8

"""
AioTest 随机加载形状示例

这个示例展示了如何实现随机加载形状，适合测试系统在不稳定负载下的性能表现

运行方式:
    py -m aiotest -f examples/load_shape/random_load_shape.py --loglevel DEBUG

运行时间: 120 秒
"""

import random

from aiotest import HttpUser, LoadUserShape, logger


class TestUser(HttpUser):
    """测试用户类"""
    host = "https://httpbin.org"
    wait_time = (1, 3)

    async def test_request(self):
        """测试请求"""
        async with self.client.get("/headers", name="Get Headers") as resp:
            assert resp.status == 200
            logger.info("请求成功")


class RandomLoadShape(LoadUserShape):
    """
    随机加载形状

    模拟随机的负载变化，适合测试系统在不稳定负载下的性能表现
    """
    max_users = 20
    min_users = 5
    max_duration = 120  # 运行 120 秒后停止

    def tick(self):
        """计算当前应该使用的用户数和生成速率"""
        run_time = self.get_run_time()

        if run_time >= self.max_duration:
            return None

        user_count = random.randint(self.min_users, self.max_users)
        rate = random.uniform(1, 5)

        return (user_count, rate)
