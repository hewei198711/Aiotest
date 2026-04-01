# encoding: utf-8

"""
AioTest 权重和等待时间示例文件

演示如何使用权重和不同类型的 wait_time 配置进行负载测试。

运行方式:
    aiotest -f examples/weight_and_wait.py
    aiotest -f examples/weight_and_wait.py --show-users-wight

使用 DEBUG 日志级别查看详细信息:
    aiotest -f examples/weight_and_wait.py --loglevel DEBUG

访问 Prometheus 监控:
    测试运行时访问 http://localhost:8089 查看性能指标
    默认端口为 8089，可通过 --prometheus-port 参数修改

功能说明:
    - 定义 4 个不同权重的用户类
    - 演示 4 种不同类型的 wait_time 配置
    - 每个用户类模拟不同的访问模式
    - 使用权重控制每个用户类在总负载中的比例

wait_time 类型说明:
    1. 固定值: wait_time = 2.0 (固定等待2秒)
    2. 随机范围: wait_time = (1, 3) (1-3秒之间随机)
    3. Lambda 函数: wait_time = lambda: random.uniform(1, 3)
    4. 协程函数: wait_time = async_wait_func (自定义异步函数)

用户类权重说明:
    - 权重越高的用户类，启动的虚拟用户数量越多
    - weight 属性控制该用户类在总用户中的比例
    - 所有用户类的 weight 默认为 1
"""

import random

from aiotest import HttpUser, LoadUserShape

# ============================================================================
# 用户类 1: 固定等待时间 (高频访问)
# ============================================================================


class UserFixedWait(HttpUser):
    """
    固定等待时间的用户类

    使用固定值的 wait_time，适合模拟稳定访问模式的用户。
    权重为 5，表示在总用户中占比较高。
    """

    # 目标服务器地址
    host = "https://httpbin.org"

    # 固定等待时间：每次任务执行后固定等待 4 秒
    wait_time = 4.0

    # 用户权重：5（占总用户的 50%）
    weight = 5

    async def test_get_ip(self):
        """获取 IP 地址"""
        async with self.client.get(endpoint="/ip", name="FixedWait: Get IP") as resp:
            assert resp.status == 200

# ============================================================================
# 用户类 2: 随机范围等待时间 (中频访问)
# ============================================================================


class UserRandomRangeWait(HttpUser):
    """
    随机范围等待时间的用户类

    使用随机范围的 wait_time，适合模拟不规律访问模式的用户。
    权重为 3，表示在总用户中占中等比例。
    """

    host = "https://httpbin.org"

    # 随机范围等待时间：每次任务执行后等待 1-3 秒之间的随机值
    wait_time = (3, 4)

    # 用户权重：3（占总用户的 30%）
    weight = 3

    async def test_post_json(self):
        """发送 POST 请求"""
        payload = {"action": "random_wait", "value": random.randint(1, 100)}
        async with self.client.post(endpoint="/post", json=payload, name="RandomWait: POST JSON") as resp:
            assert resp.status == 200


# ============================================================================
# 用户类 3: Lambda 函数等待时间 (低频访问)
# ============================================================================

class UserLambdaWait(HttpUser):
    """
    Lambda 函数等待时间的用户类

    使用 Lambda 函数定义 wait_time，适合根据业务逻辑动态计算等待时间。
    权重为 1，表示在总用户中占比较低。
    """

    host = "https://httpbin.org"

    # Lambda 函数等待时间：每次调用时动态计算等待时间
    # 使用 random.uniform 返回 2.5 到 3.5 秒之间的随机值
    # 注意：使用 *args 接收任意数量参数，兼容无参数调用
    wait_time = lambda *args: random.uniform(2.5, 3.5)

    # 用户权重：1（占总用户的 10%）
    weight = 1

    async def test_delay(self):
        """测试延迟请求（模拟长耗时操作）"""
        # 延迟 1 秒
        async with self.client.get(endpoint="/delay/1", name="LambdaWait: Delay 1s") as resp:
            assert resp.status == 200


# ============================================================================
# 用户类 4: 异步函数等待时间 (超低频访问)
# ============================================================================

class UserAsyncWait(HttpUser):
    """
    异步函数等待时间的用户类

    使用异步协程函数定义 wait_time，可以在等待时执行异步操作。
    权重为 1，表示在总用户中占比较低。
    """

    host = "https://httpbin.org"

    # 异步函数等待时间：每次调用时异步计算等待时间
    # 可以在函数内部执行其他异步操作（如查询数据库、缓存等）
    # 注意：使用 *args 接收任意数量参数，兼容无参数调用
    async def async_wait_time(self, *args):
        """自定义异步等待时间函数，返回 3.5 到 4.5 秒之间的随机值"""
        return random.uniform(3.5, 4.5)

    wait_time = async_wait_time

    # 用户权重：1（占总用户的 10%）
    weight = 1

    async def test_post_json(self):
        """发送 POST 请求"""
        payload = {"user_type": "async_wait", "timestamp": random.random()}
        async with self.client.post(endpoint="/post", json=payload, name="AsyncWait: POST JSON") as resp:
            assert resp.status == 200


# ============================================================================
# 负载形状定义
# ============================================================================

class TestLoadShape(LoadUserShape):
    """
    负载形状定义

    根据用户类的权重分配虚拟用户数量。
    总用户数为 10，分配如下：
    - UserFixedWait (权重 5): 5 个用户
    - UserRandomRangeWait (权重 3): 3 个用户
    - UserLambdaWait (权重 1): 1 个用户
    - UserAsyncWait (权重 1): 1 个用户
    """

    # 定义负载阶段
    stages = [
        {"duration": 60, "user_count": 10, "rate": 5},
    ]

    # 更复杂的负载形状示例:
    # stages = [
    #     {"duration": 30, "user_count": 20, "rate": 2},   # 0-30秒：20个用户，每秒启动2个
    #     {"duration": 60, "user_count": 50, "rate": 5},   # 30-60秒：增加到50个用户
    #     {"duration": 90, "user_count": 100, "rate": 10}, # 60-90秒：增加到100个用户
    #     {"duration": 120, "user_count": 50, "rate": 5},  # 90-120秒：减少到50个用户
    #     {"duration": 150, "user_count": 20, "rate": 2},  # 120-150秒：减少到20个用户
    # ]

    def tick(self):
        """
        计算当前应该使用的用户数和生成速率

        Returns:
            tuple: (user_count, rate) 或 None
        """
        run_time = self.get_run_time()

        for stage in self.stages:
            if run_time < stage["duration"]:
                return (stage["user_count"], stage["rate"])

        return None


# ============================================================================
# wait_time 使用说明
# ============================================================================

"""
wait_time 参数支持 4 种类型：

1. 固定值 (float):
   wait_time = 2.0
   - 每次任务执行后固定等待 2 秒
   - 适合稳定、可预测的访问模式

2. 随机范围 (tuple):
   wait_time = (1, 3)
   - 每次任务执行后等待 1-3 秒之间的随机值
   - 适合模拟真实用户的不规律访问

3. Lambda 函数:
   wait_time = lambda *args: random.uniform(1, 3)
   - 每次调用时执行 Lambda 函数计算等待时间
   - 可以根据自定义逻辑动态计算
   - 使用 *args 接收任意数量参数，兼容无参数调用

4. 异步协程函数:
   wait_time = async_wait_time  # 定义为类方法或实例方法
   async def async_wait_time(self, *args):
       return random.uniform(0.5, 1.5)
   - 每次调用时执行异步函数计算等待时间
   - 可以在函数内部执行异步操作（如查询配置、缓存等）
   - 必须定义为类方法或实例方法
   - 使用 *args 接收任意数量参数，兼容无参数调用
"""
