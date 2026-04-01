# encoding: utf-8

"""
AioTest 阶梯式加载形状示例

这个示例展示了如何实现阶梯式加载形状，适合测试系统在逐步增加负载时的性能表现

加载形状示意图:
    用户数
      ^
    20|                   ____
      |                  |    |
    15|            ____  |    |
      |           |           |
    10|      ____|            |
      |     |                 |
    5 |____|                  |
      +-------------------------> 时间
       0    30   60   90  120

运行方式:
    aiotest -f examples/load_shape/step_soad_shape.py --loglevel DEBUG

运行时间: 120 秒
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


class StepLoadShape(LoadUserShape):
    """
    阶梯式加载形状

    逐步增加用户数，适合测试系统在逐步增加负载时的性能表现
    """
    stages = [
        {"duration": 30, "user_count": 5, "rate": 1},  # 0-30秒：5个用户，每秒1个
        {"duration": 60, "user_count": 10, "rate": 2},  # 30-60秒：10个用户，每秒2个
        {"duration": 90, "user_count": 15, "rate": 3},  # 60-90秒：15个用户，每秒3个
        {"duration": 120, "user_count": 20, "rate": 4},  # 90-120秒：20个用户，每秒4个
    ]

    def tick(self):
        """计算当前应该使用的用户数和生成速率"""
        run_time = self.get_run_time()

        for stage in self.stages:
            if run_time < stage["duration"]:
                return (stage["user_count"], stage["rate"])

        return None


# 主加载形状类
class LoadShape(StepLoadShape):
    """使用阶梯式加载形状"""
    pass
