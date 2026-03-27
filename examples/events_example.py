# encoding: utf-8

"""
AioTest 事件系统示例文件

演示如何使用 aiotest 的事件系统来监听和处理测试生命周期中的各种事件。

运行方式:
    py -m aiotest -f examples/events_example.py

使用 DEBUG 日志级别查看详细信息:
    py -m aiotest -f examples/events_example.py --loglevel DEBUG

访问 Prometheus 监控:
    测试运行时访问 http://localhost:8089 查看性能指标
    默认端口为 8089，可通过 --prometheus-port 参数修改

功能说明:
    - 演示所有预定义事件的使用
    - 展示如何注册事件处理器
    - 展示不同优先级的事件处理
    - 展示同步和异步事件处理器
    - 展示事件处理器的参数接收

预定义事件:
    1. init_events - 初始化事件
    2. test_start - 测试开始事件
    3. test_stop - 测试停止事件
    4. test_quit - 测试退出事件
    5. startup_completed - 启动完成事件
    6. request_metrics - 请求指标事件
    7. worker_request_metrics - worker 请求指标事件（仅 master 节点）
"""

from aiotest import (HttpUser, LoadUserShape, init_events, request_metrics,
                     startup_completed, test_quit, test_start, test_stop,
                     worker_request_metrics)

# ============================================================================
# 使用装饰器注册事件处理器
# ============================================================================

# 1. 初始化事件处理器


@init_events.handler(priority=0)
async def on_init_events(**kwargs):
    """初始化事件处理器 - 在系统初始化时触发"""
    print("🚀 [init_events] 系统初始化中...")

# 2. 测试开始事件处理器


@test_start.handler(priority=0)
async def on_test_start(**kwargs):
    """测试开始事件处理器 - 在测试开始时触发"""
    print("▶️  [test_start] 测试开始")

# 3. 测试停止事件处理器


@test_stop.handler(priority=0)
async def on_test_stop(**kwargs):
    """测试停止事件处理器 - 在测试停止时触发"""
    print("⏹️  [test_stop] 测试停止")

# 4. 测试退出事件处理器


@test_quit.handler(priority=0)
async def on_test_quit(**kwargs):
    """测试退出事件处理器 - 在测试退出时触发"""
    print("👋 [test_quit] 测试退出")

# 5. 启动完成事件处理器


@startup_completed.handler(priority=0)
async def on_startup_completed(**kwargs):
    """启动完成事件处理器 - 在所有用户启动完成后触发"""
    print("✅ [startup_completed] 所有用户已启动完成")

# 6. 请求指标事件处理器（带优先级）


@request_metrics.handler(priority=10)  # 最高优先级：慢请求检测
async def on_request_metrics_slow(**kwargs):
    """请求指标事件处理器 - 记录慢请求"""
    metrics = kwargs.get('metrics')
    if metrics and metrics.duration > 1000:
        print(
            f"⚠️  [request_metrics] 慢请求: {
                metrics.method} {
                metrics.endpoint}, 耗时: {
                metrics.duration:.0f}ms")


@request_metrics.handler(priority=5)  # 中等优先级：错误请求检测
async def on_request_metrics_error(**kwargs):
    """请求指标事件处理器 - 记录错误请求"""
    metrics = kwargs.get('metrics')
    if metrics and metrics.status_code >= 400:
        print(
            f"❌ [request_metrics] 错误请求: {
                metrics.method} {
                metrics.endpoint}, 状态码: {
                metrics.status_code}")


@request_metrics.handler(priority=0)  # 默认优先级：常规日志
async def on_request_metrics(**kwargs):
    """请求指标事件处理器 - 每次请求完成后触发"""
    metrics = kwargs.get('metrics')
    if metrics:
        print(
            f"📈 [request_metrics] 请求完成: {
                metrics.method} {
                metrics.endpoint}, 状态: {
                metrics.status_code}, 耗时: {
                    metrics.duration:.0f}ms")

# 7. Worker 请求指标事件处理器（仅 master 节点）


@worker_request_metrics.handler(priority=0)
async def on_worker_request_metrics(**kwargs):
    """Worker 请求指标事件处理器 - 接收来自 worker 的指标"""
    worker_id = kwargs.get('worker_id', 'unknown')
    print(f"📡 [worker_request_metrics] 收到 worker {worker_id} 的指标")


# ============================================================================
# 用户类定义
# ============================================================================

class EventsUser(HttpUser):
    """
    事件系统示例用户类

    演示如何在测试过程中触发各种事件。

    每个请求完成后都会触发 request_metrics 事件，
    事件处理器会记录请求信息。
    """

    # 目标服务器地址
    host = "https://httpbin.org"

    # 请求间隔时间：1-2秒之间随机
    wait_time = (1, 2)

    async def test_get_root(self):
        """测试 GET 请求"""
        async with self.client.get(endpoint="/get") as resp:
            assert resp.status == 200
            print(f"✅ 请求成功: GET /get")

    async def test_post_data(self):
        """测试 POST 请求"""
        async with self.client.post(
            endpoint="/post",
            json={"key": "value"}
        ) as resp:
            assert resp.status == 200
            print(f"✅ 请求成功: POST /post")

    async def test_get_delay(self):
        """测试带延迟的请求"""
        async with self.client.get(endpoint="/delay/1") as resp:
            assert resp.status == 200
            print(f"✅ 请求成功: GET /delay/1 (慢请求)")

    async def test_get_status_404(self):
        """测试 404 错误"""
        async with self.client.get(endpoint="/status/404"):
            print(f"⚠️  请求返回 404: GET /status/404")

    async def test_get_status_500(self):
        """测试 500 错误"""
        async with self.client.get(endpoint="/status/500"):
            print(f"❌ 请求返回 500: GET /status/500")


# ============================================================================
# 负载形状定义
# ============================================================================

class EventsLoadShape(LoadUserShape):
    """
    负载形状定义

    设置较短的测试时间，便于快速查看所有事件触发。
    """

    stages = [
        {"duration": 10, "user_count": 1, "rate": 1},   # 0-10秒：1个用户
        {"duration": 20, "user_count": 2, "rate": 2},  # 10-20秒：增加到2个用户
        {"duration": 30, "user_count": 1, "rate": 1},   # 20-30秒：减少到1个用户
    ]

    def tick(self):
        """计算当前应该使用的用户数和生成速率"""
        run_time = self.get_run_time()

        for stage in self.stages:
            if run_time < stage["duration"]:
                return (stage["user_count"], stage["rate"])

        return None


# ============================================================================
# 事件系统使用说明
# ============================================================================

"""
事件系统使用说明（装饰器模式）：

1. 事件类型：
   - init_events: 初始化时触发
   - test_start: 测试开始时触发
   - test_stop: 测试停止时触发
   - test_quit: 测试退出时触发
   - startup_completed: 所有用户启动完成后触发
   - request_metrics: 每次请求完成后触发（频繁）
   - worker_request_metrics: master 接收 worker 指标时触发

2. 使用装饰器注册事件处理器：
   from aiotest import test_start

   @test_start.handler(priority=0)
   async def my_handler(**kwargs):
       print("测试开始")

3. 手动注册事件处理器：
   from aiotest import test_start

   async def my_handler(**kwargs):
       print("测试开始")

   await test_start.add_handler(my_handler, priority=0)

4. 优先级：
   - 数值越大，优先级越高
   - 默认优先级为 0
   - 高优先级处理器先执行

5. 事件处理器参数：
   async def handler(**kwargs):
       # kwargs 包含事件相关的参数
       pass

6. request_metrics 事件参数：
   - request_id: 请求ID
   - method: HTTP方法
   - endpoint: 请求端点
   - status_code: 状态码
   - duration: 请求耗时（毫秒）

7. 装饰器模式优势：
   - 代码更简洁，注册逻辑与处理器定义在一起
   - 统一通过事件钩子对象注册，接口一致
   - 自动管理事件处理器注册
   - 支持优先级设置
   - 避免手动调用 add_handler()
"""
