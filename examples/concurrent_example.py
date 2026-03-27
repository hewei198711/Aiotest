# encoding: utf-8

"""
AioTest 并发执行模式示例文件

演示如何使用并发执行模式进行 HTTP 负载测试，以及如何使用 name 参数自定义请求名称。

运行方式:
    py -m aiotest -f examples/concurrent_example.py

使用 DEBUG 日志级别查看详细信息:
    py -m aiotest -f examples/concurrent_example.py --loglevel DEBUG

访问 Prometheus 监控:
    测试运行时访问 http://localhost:8089 查看性能指标
    默认端口为 8089，可通过 --prometheus-port 参数修改

功能说明:
    - 使用并发执行模式模拟真实用户并发请求
    - 使用 @weight 装饰器设置任务权重
    - 使用 name 参数自定义请求名称，便于统计和监控
    - 设置负载形状，控制用户数量和生成速率

并发执行模式特点:
    - 任务并行执行，不受顺序限制
    - 可以设置最大并发任务数 (max_concurrent_tasks)
    - 支持任务权重，权重越高的任务执行频率越高
    - 适合模拟商城首页多个接口的并发请求

name 参数说明:
    - 在请求中使用 name 参数可以自定义请求名称
    - name 会显示在日志、指标和 Prometheus 监控中
    - 便于区分不同的请求类型和业务场景
    - 推荐使用有意义的名称，如 "用户登录"、"获取商品列表" 等

并发限制说明:
    1. HTTP 连接池限制（重要！）:
       - limit: 1000（全局最大连接数，所有主机共享）
       - limit_per_host: 1000（每个主机最大连接数，本示例已配置）
       - 注意：本示例为单主机测试，已配置为 1000/1000

    2. limit 与 limit_per_host 的区别:

       【limit - 全局连接池上限】
       - 作用：限制整个客户端的并发连接总数
       - 包含所有主机的连接
       - 限制总资源使用量
       - 示例：limit=1000 表示所有主机加起来最多1000个并发连接

       【limit_per_host - 单主机连接上限】
       - 作用：限制对单个主机的并发连接数
       - 防止某个主机耗尽所有连接
       - 保护目标服务器不被压垮
       - 示例：limit_per_host=100 表示对同一个主机最多100个并发连接

    3. 实际并发计算规则:

       规则1：单个主机的并发 ≤ limit_per_host
       规则2：所有主机的并发总和 ≤ limit
       规则3：取两者中更严格的限制

    4. 具体示例:

       示例1：单主机测试
       配置：limit=1000, limit_per_host=100
       测试：访问 https://httpbin.org
       结果：最多 100 个并发（受 limit_per_host 限制）

       示例2：多主机测试（2个主机）
       配置：limit=1000, limit_per_host=100
       测试：
         - 50% 请求访问 https://httpbin.org（主机A）
         - 50% 请求访问 https://api.example.com（主机B）
       结果：
         - 主机A最多 100 个并发
         - 主机B最多 100 个并发
         - 总计最多 200 个并发

       示例3：多主机测试（10个主机）
       配置：limit=1000, limit_per_host=100
       测试：访问 10 个不同的主机
       结果：最多 1000 个并发（受 limit 限制）
       计算：10主机 × 100并发/主机 = 1000，正好达到全局上限

       示例4：配置不当的情况
       配置：limit=500, limit_per_host=1000
       测试：访问单个主机
       结果：最多 500 个并发（受 limit 限制）
       注意：limit_per_host 设置过高没有意义，因为全局 limit 更小

    5. 最佳实践建议:

       单主机压测（本示例使用）:
       configure_connector(limit=1000, limit_per_host=1000)

       多主机压测（3-5个主机）:
       configure_connector(limit=1000, limit_per_host=200)

       多主机压测（10+个主机）:
       configure_connector(limit=2000, limit_per_host=100)

       防止单主机被压垮:
       configure_connector(limit=1000, limit_per_host=50)
       # 即使 limit=1000，单个主机最多50并发，保护服务器

       超大规模压测（推荐配置）:
       configure_connector(limit=5000, limit_per_host=500)

    6. 如何调整并发限制:
       from aiotest import configure_connector

       # 增加限制
       configure_connector(limit=2000, limit_per_host=200)

       # 减少限制（保护服务器）
       configure_connector(limit=50, limit_per_host=10)

    7. 系统资源限制:
       - 文件描述符限制 (ulimit -n)
         - 系统自动设置为 10000
         - 如需更大值：ulimit -n 65535
       - 服务器并发连接限制
       - 网络带宽限制
"""

from aiotest import (ExecutionMode, HttpUser, LoadUserShape,
                     configure_connector, weight)

# ============================================================================
# 并发执行模式用户类示例
# ============================================================================

# 配置 HTTP 连接池（单主机测试，提高并发上限）
configure_connector(limit=1000, limit_per_host=1000)


class ConcurrentUser(HttpUser):
    """
    并发执行模式的用户类

    模拟真实用户在电商网站上的并发访问行为。

    使用场景:
        - 商城首页：用户同时加载多个模块（轮播图、商品列表、广告等）
        - 仪表板：同时加载多个图表和数据
        - 移动端 App：同时请求多个接口初始化页面

    类属性说明:
        host: 目标服务器地址
        wait_time: 任务执行间隔时间
        execution_mode: 任务执行模式（CONCURRENT = 并发）
        max_concurrent_tasks: 每个用户最大并发任务数
                           注意：这是每个用户的并发限制，不是所有用户的总和
                           例如：10个用户，max_concurrent_tasks=3，理论上最多30个任务并发执行
        weight: 用户权重（在多用户类场景中控制比例）
    """

    # 目标服务器地址
    host = "https://httpbin.org"

    # 请求间隔时间：2-3秒之间随机
    wait_time = (2, 3)

    # 注意：连接池已配置为 limit=1000, limit_per_host=1000
    # 适用于单主机高并发测试场景

    # 执行模式：并发执行
    execution_mode = ExecutionMode.CONCURRENT

    # 最大并发任务数：同时最多执行 2 个任务
    max_concurrent_tasks = 2

    async def on_start(self):
        """
        用户启动时的初始化方法
        模拟用户登录并获取会话信息
        """
        await super().on_start()

        # 模拟登录请求，获取用户会话
        async with self.client.post(
            endpoint="/post",
            json={"action": "login", "username": f"user_{id(self)}"},
            name="用户登录"  # 自定义请求名称
        ) as resp:
            data = await resp.json()
            # 模拟保存会话信息
            self.session_id = data.get('data', 'session_001')

    # ============================================================================
    # 高频任务（使用 @weight 装饰器设置权重）
    # ============================================================================

    @weight(8)  # 高频任务，权重为 8
    async def test_get_home_page(self):
        """
        获取首页内容

        模拟用户访问商城首页，加载主要信息。
        使用 name 参数自定义请求名称为 "获取首页"。
        """
        async with self.client.get(
            endpoint="/get",
            name="获取首页"  # 自定义请求名称
        ) as resp:
            assert resp.status == 200

    @weight(6)  # 高频任务，权重为 6
    async def test_get_product_list(self):
        """
        获取商品列表

        模拟用户浏览商品列表。
        使用 name 参数自定义请求名称为 "获取商品列表"。
        """
        async with self.client.get(
            endpoint="/get?page=1&size=20",
            name="获取商品列表"  # 自定义请求名称
        ) as resp:
            assert resp.status == 200

    # ============================================================================
    # 中频任务
    # ============================================================================

    @weight(4)  # 中频任务，权重为 4
    async def test_search_product(self):
        """
        搜索商品

        模拟用户搜索商品。
        使用 name 参数自定义请求名称为 "搜索商品"。
        动态参数模拟不同的搜索关键词。
        """
        import random
        keywords = ["手机", "电脑", "耳机", "键盘", "鼠标", "显示器"]
        keyword = random.choice(keywords)

        async with self.client.get(
            endpoint=f"/get?q={keyword}",
            name=f"搜索商品: {keyword}"  # 动态请求名称
        ) as resp:
            assert resp.status == 200

    @weight(3)  # 中频任务，权重为 3
    async def test_get_product_detail(self):
        """
        获取商品详情

        模拟用户查看商品详情。
        使用 name 参数自定义请求名称为 "获取商品详情"。
        """
        async with self.client.get(
            endpoint="/get?product_id=12345",
            name="获取商品详情"  # 自定义请求名称
        ) as resp:
            assert resp.status == 200

    # ============================================================================
    # 低频任务
    # ============================================================================

    @weight(2)  # 低频任务，权重为 2
    async def test_add_to_cart(self):
        """
        添加商品到购物车

        模拟用户将商品添加到购物车。
        使用 name 参数自定义请求名称为 "添加到购物车"。
        """
        payload = {
            "product_id": "12345",
            "quantity": 1,
            "session_id": getattr(self, 'session_id', 'unknown')
        }
        async with self.client.post(
            endpoint="/post",
            json=payload,
            name="添加到购物车"  # 自定义请求名称
        ) as resp:
            assert resp.status == 200

    @weight(1)  # 低频任务，权重为 1
    async def test_get_user_info(self):
        """
        获取用户信息

        模拟用户查看个人信息。
        使用 name 参数自定义请求名称为 "获取用户信息"。
        """
        async with self.client.get(
            endpoint="/get",
            name="获取用户信息"  # 自定义请求名称
        ) as resp:
            assert resp.status == 200

    @weight(1)  # 低频任务，权重为 1
    async def test_submit_order(self):
        """
        提交订单

        模拟用户提交订单。
        使用 name 参数自定义请求名称为 "提交订单"。
        """
        payload = {
            "order_id": f"order_{id(self)}",
            "total_amount": 99.99,
            "session_id": getattr(self, 'session_id', 'unknown')
        }
        async with self.client.post(
            endpoint="/post",
            json=payload,
            name="提交订单"  # 自定义请求名称
        ) as resp:
            assert resp.status == 200


# ============================================================================
# 负载形状定义
# ============================================================================

class TestLoadShape(LoadUserShape):
    """
    负载形状定义

    定义测试运行过程中的用户数量和生成速率变化。

    示例场景：
        - 预热期：缓慢增加用户，模拟系统预热
        - 峰值期：保持最大用户数，模拟高负载
        - 冷却期：缓慢减少用户，模拟系统冷却
    """

    # 定义负载阶段
    stages = [
        {"duration": 20, "user_count": 1, "rate": 1},   # 0-20秒：1个用户，每秒启动1个（预热）
        {"duration": 40, "user_count": 2, "rate": 2},  # 20-40秒：增加到2个用户（峰值）
        {"duration": 60, "user_count": 1, "rate": 1},   # 40-60秒：减少到1个用户（冷却）
    ]

    def tick(self):
        """
        计算当前应该使用的用户数和生成速率

        Returns:
            tuple: (user_count, rate) 当前应该使用的用户数和速率
            None: 测试应该结束
        """
        run_time = self.get_run_time()

        for stage in self.stages:
            if run_time < stage["duration"]:
                return (stage["user_count"], stage["rate"])

        return None


# ============================================================================
# 并发执行模式使用说明
# ============================================================================

"""
并发执行模式 (CONCURRENT) 使用说明：

1. 设置执行模式:
   execution_mode = ExecutionMode.CONCURRENT

2. 设置最大并发任务数:
   max_concurrent_tasks = 3  # 每个用户最多同时执行3个任务（不是所有用户的总和）

3. 使用 @weight 装饰器设置任务权重:
   @weight(5)  # 权重越高，执行频率越高
   async def test_task(self):
       pass

4. 使用 name 参数自定义请求名称:
   async with self.client.get(endpoint="/get", name="自定义名称") as resp:
       pass

5. 并发执行流程:
   - 用户启动时执行 on_start()
   - 根据权重随机选择任务
   - 并发执行最多 max_concurrent_tasks 个任务
   - 每个任务执行完后等待 wait_time
   - 重复执行直到用户停止

6. name 参数的作用:
   - 在日志中显示自定义名称
   - 在 Prometheus 监控中按名称分组统计
   - 便于识别不同业务场景的性能指标
   - 推荐使用有意义的名称，如 "用户登录"、"获取商品列表"

7. 动态 name 参数:
   # 可以在 name 中使用变量或表达式
   name=f"搜索商品: {keyword}"
   name=f"用户: {user_id}"

8. 适用场景:
   - 首页多模块并发加载
   - 仪表板多图表并发请求
   - 移动端 App 初始化
   - 任何需要同时请求多个接口的场景
"""
