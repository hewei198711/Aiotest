# encoding: utf-8

"""
AioTest 峰值式加载形状示例

这个示例展示了如何实现峰值式加载形状，适合测试系统在突发流量下的性能表现

加载形状示意图:
    用户数
      ^
      |          _____          _____
    20|         |     |        |     |
      |         |     |        |     |
    5 | ________|     |________|     |________
      +---------------------------------> 时间
       0    15   30   45   60   75   90

运行方式:
    aiotest -f examples/load_shape/peak_load_shape.py --loglevel DEBUG

运行时间: 180 秒
"""

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


class PeakLoadShape(LoadUserShape):
    """
    峰值式加载形状

    模拟突然的高负载场景，适合测试系统在突发流量下的性能表现
    """
    base_users = 5
    peak_users = 20
    peak_interval = 60  # 每60秒出现一次峰值
    peak_duration = 15  # 峰值持续15秒
    max_duration = 180  # 最多运行180秒

    def tick(self):
        """计算当前应该使用的用户数和生成速率"""
        run_time = self.get_run_time()

        if run_time >= self.max_duration:
            return None

        cycle = int(run_time / self.peak_interval)
        peak_start = cycle * self.peak_interval
        peak_end = peak_start + self.peak_duration

        if peak_start <= run_time < peak_end:
            return (self.peak_users, 5)
        else:
            return (self.base_users, 1)
