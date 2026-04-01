# encoding: utf-8

"""
AioTest 基础示例文件

这是一个简单的 aiotest 使用示例，展示如何进行 HTTP 负载测试。

运行方式:
    aiotest -f examples/basic.py

使用 DEBUG 日志级别查看详细信息:
    aiotest -f examples/basic.py --loglevel DEBUG

访问 Prometheus 监控:
    测试运行时访问 http://localhost:8089 查看性能指标
    默认端口为 8089，可通过 --prometheus-port 参数修改

功能说明:
    - 使用 httpbin.org 作为测试目标（一个 HTTP 请求/响应测试服务）
    - 定义 7 个测试任务，演示各种 HTTP 请求方法
    - 支持顺序执行和并发执行两种模式
    - 设置负载形状，控制用户数量和生成速率

配置说明:
    - host: 目标服务器地址
    - wait_time: 任务执行间隔时间（支持固定值、随机范围、自定义函数）
    - execution_mode: 任务执行模式（SEQUENTIAL/CONCURRENT）
    - stages: 负载形状配置，定义不同阶段的用户数和速率
"""

from aiotest import ExecutionMode, HttpUser, LoadUserShape


class TestUser(HttpUser):
    """
    基础用户类，执行对 httpbin.org 测试服务的 HTTP 请求

    这个示例展示了 aiotest 的基本用法：
    - 定义用户类继承 HttpUser
    - 使用 test_ 开头或 _test 结尾的协程函数定义任务
    - 设置 host 和 wait_time 配置
    - 支持顺序执行（默认）和并发执行两种模式
    - 使用 on_start() 方法进行初始化（如获取 token）
    - 在任务中使用认证信息

    httpbin.org 是一个 HTTP 请求和响应测试服务，支持各种 HTTP 方法和功能测试。
    官网: https://httpbin.org

    类属性说明:
        host: 目标服务器地址（必需）
        wait_time: 任务执行间隔时间
                  - 固定值: wait_time = 2.0 (固定等待2秒)
                  - 随机范围: wait_time = (1, 3) (1-3秒之间随机)
                  - 支持函数/协程函数: wait_time = lambda: random.uniform(1, 3)
        execution_mode: 任务执行模式
                       - ExecutionMode.SEQUENTIAL: 顺序执行（默认）
                       - ExecutionMode.CONCURRENT: 并发执行

    生命周期方法:
        on_start(): 用户启动时调用一次，用于初始化资源
                   - 必须先调用 await super().on_start() 初始化 HTTP 客户端
                   - 适合用于：获取 token、加载测试数据、建立连接等
        on_stop(): 用户停止时调用一次，用于清理资源
                  - 适合用于：关闭连接、保存状态、释放资源等
                  - 必须最后调用 await super().on_stop() 关闭 HTTP 客户端

    示例场景:
        模拟真实用户登录流程：
        1. on_start() - 调用登录接口获取 token
        2. test_xxx() - 使用 token 访问需要认证的接口
        3. on_stop() - 清理用户状态
    """

    # 目标服务器地址（必需）
    host = "https://httpbin.org"

    # 请求间隔时间（1-3秒之间随机）
    wait_time = (1, 3)

    # 执行模式（默认顺序执行）
    execution_mode = ExecutionMode.SEQUENTIAL

    async def on_start(self):
        """
        用户启动时的初始化方法,仅执行一次

        在所有测试任务开始前执行，用于：
        - 初始化用户状态
        - 获取认证 token
        - 准备测试数据
        - 建立必要的连接

        注意：必须先调用父类的 on_start() 方法，确保 HTTP 客户端正确初始化
        """
        # 调用父类方法初始化 HTTP 客户端
        await super().on_start()

        # 模拟获取 token 的场景
        # 在真实场景中，这里会调用登录接口获取 token
        async with self.client.post(endpoint="/post", name="Login & Get Token") as resp:
            data = await resp.json()
            assert resp.status == 200

            # 从响应中提取 token（模拟真实场景）
            # httpbin.org 的 /post 接口会返回我们发送的数据
            # 我们假设服务器返回了一个 token
            self.auth_token = f"Bearer token_{data.get('data', 'mock-token')}"

            # 也可以保存其他用户信息
            self.user_id = data.get('data', 'user_001')

        # 保存 token 以便后续请求使用（可选）
        # self.client.default_headers['Authorization'] = self.auth_token

    async def test_authenticated_request(self):
        """
        使用 Token 的认证请求

        演示如何在请求中使用认证 token。
        在真实场景中，会发送包含 Authorization 头的请求。
        """
        # 使用在 on_start 中获取的 token
        headers = {
            "Authorization": self.auth_token,
            "User-ID": self.user_id
        }

        async with self.client.get(endpoint="/headers", headers=headers, name="Authenticated Request") as resp:
            data = await resp.json()
            assert resp.status == 200
            # 验证我们的认证信息被正确发送
            assert "headers" in data
            # httpbin 会返回我们发送的请求头（转换成小写）
            # Authorization 可能会被转换成小写
            sent_headers = data["headers"]
            assert "Authorization" in sent_headers or "authorization" in sent_headers

    async def test_get_ip(self):
        """
        获取客户端 IP 信息

        测试 GET 请求，验证响应状态码和响应数据结构。
        """
        async with self.client.get(endpoint="/ip", name="Get IP") as resp:
            data = await resp.json()
            # 验证状态码
            assert resp.status == 200
            # 验证响应数据包含 origin 字段
            assert "origin" in data
            # 验证 IP 地址不为空
            assert data["origin"] is not None

    async def test_get_headers(self):
        """
        获取请求头信息

        测试 GET 请求，验证响应中包含完整的请求头信息。
        """
        async with self.client.get(endpoint="/headers", name="Get Headers") as resp:
            data = await resp.json()
            assert resp.status == 200
            assert "headers" in data
            assert isinstance(data["headers"], dict)

    async def test_get_user_agent(self):
        """
        获取 User-Agent 信息

        测试 GET 请求，验证 User-Agent 请求头。
        """
        async with self.client.get(endpoint="/user-agent", name="Get User-Agent") as resp:
            data = await resp.json()
            assert resp.status == 200
            assert "user-agent" in data
            assert len(data["user-agent"]) > 0

    async def test_delay(self):
        """
        模拟延迟响应（2秒）

        测试 GET 请求，验证服务器可以正确处理延迟响应。
        httpbin.org/delay/{seconds} 会延迟指定秒数后返回响应。
        """
        async with self.client.get(endpoint="/delay/2", name="Delayed Request") as resp:
            data = await resp.json()
            assert resp.status == 200
            # httpbin /delay/2 只是延迟响应，返回的数据结构与 /get 相同
            assert "url" in data
            assert data["url"] == "https://httpbin.org/delay/2"

    async def test_post_json(self):
        """
        发送 JSON POST 请求

        测试 POST 请求，验证可以正确发送和接收 JSON 数据。
        """
        payload = {"key": "value", "message": "Hello from AioTest"}
        async with self.client.post(endpoint="/post", json=payload, name="POST JSON") as resp:
            data = await resp.json()
            assert resp.status == 200
            assert "json" in data
            # 验证服务器正确解析了我们发送的 JSON 数据
            assert data["json"]["key"] == "value"
            assert data["json"]["message"] == "Hello from AioTest"

    async def test_status_404(self):
        """
        测试 404 状态码

        测试错误处理，验证可以正确处理 404 Not Found 响应。
        """
        async with self.client.get(endpoint="/status/404", name="Status 404") as resp:
            assert resp.status == 200  # 实际返回404，断言失败会记录到错误统计中

    async def test_status_500(self):
        """
        测试 500 状态码

        测试错误处理，验证可以正确处理 500 Internal Server Error 响应。
        """
        async with self.client.get(endpoint="/status/500", name="Status 500") as resp:
            assert resp.status == 200  # 实际返回500，断言失败会记录到错误统计中


class TestLoadShape(LoadUserShape):
    """
    基础负载形状定义

    负载形状（Load Shape）用于控制测试运行过程中的用户数量和生成速率变化。
    通过定义多个阶段（stages），可以模拟真实的负载增长和减少过程。

    属性说明:
        stages: 负载阶段列表，每个阶段包含:
               - duration: 阶段持续时间（秒）
               - user_count: 目标用户数量
               - rate: 用户生成速率（用户/秒）

    方法说明:
        tick(): 每 1 秒调用一次，返回当前应该使用的 (user_count, rate)
              返回 None 表示测试应该结束

    示例场景:
        预热期: 缓慢增加用户数，模拟系统预热
        峰值期: 保持最大用户数，模拟高负载
        冷却期: 缓慢减少用户数，模拟系统冷却

    注意事项:
        - 每个测试文件只能有一个 LoadUserShape 子类
        - tick() 方法必须返回 (user_count, rate) 元组或 None
        - duration 是相对于测试开始时间的累积时间
    """

    # 定义负载阶段
    # 示例：保持 1 个用户持续 30 秒
    stages = [
        {"duration": 30, "user_count": 1, "rate": 1},
    ]

    # 更复杂的负载形状示例:
    # stages = [
    #     {"duration": 30, "user_count": 10, "rate": 1},   # 0-30秒：10个用户，每秒启动1个
    #     {"duration": 60, "user_count": 50, "rate": 2},   # 30-60秒：增加到50个用户，每秒启动2个
    #     {"duration": 90, "user_count": 100, "rate": 5},  # 60-90秒：增加到100个用户，每秒启动5个
    #     {"duration": 120, "user_count": 50, "rate": 2},  # 90-120秒：减少到50个用户
    #     {"duration": 150, "user_count": 10, "rate": 1},  # 120-150秒：减少到10个用户
    # ]

    def tick(self):
        """
        计算当前应该使用的用户数和生成速率

        这个方法每秒被调用一次，用于获取当前时刻的负载配置。

        返回:
            tuple: (user_count, rate) 当前应该使用的用户数和速率
            None: 测试应该结束

        注意:
            - duration 是相对于测试开始时间的累积时间
            - 如果当前时间不在任何阶段内，返回 None 结束测试
        """
        run_time = self.get_run_time()

        for stage in self.stages:
            if run_time < stage["duration"]:
                return (stage["user_count"], stage["rate"])

        return None
