# encoding: utf-8

"""
AioTest 波浪式加载形状示例

这个示例展示了如何实现波浪式加载形状，适合测试系统在波动负载下的性能表现

加载形状示意图:
    用户数
      ^
    20|   *           *           *
      |  * *         * *         * *
    15| *   *       *   *       *   *
      |*     *     *     *     *     *
    5 |       *   *       *   *       *
      |        * *         * *         *
      +---------------------------------> 时间
       0    7.5   15   22.5   30   37.5

运行方式:
    aiotest -f examples/load_shape/wave_load_shape.py --loglevel DEBUG

运行时间: 120 秒
"""

import math

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


class WaveLoadShape(LoadUserShape):
    """
    波浪式加载形状

    模拟负载的周期性变化，适合测试系统在波动负载下的性能表现
    """
    max_users = 20
    min_users = 5
    period = 30  # 周期为30秒
    max_duration = 120  # 运行 120 秒后停止

    def tick(self):
        """计算当前应该使用的用户数和生成速率"""
        run_time = self.get_run_time()

        if run_time >= self.max_duration:
            return None

        user_count = int((self.max_users -
                          self.min_users) *
                         abs(math.sin(run_time *
                                      2 *
                                      math.pi /
                                      self.period)) +
                         self.min_users)
        rate = 3

        return (user_count, rate)
