# encoding: utf-8

"""
AioTest 请求成功/失败判定示例

这个示例展示了如何在 aiotest 中判断请求是否成功或失败，包括：
- HTTP 状态码判断
- 响应内容验证
- 异常处理
- 超时处理
- 重试机制
- 日志记录
- 断言结果标签

运行方式:
    aiotest -f examples/request_verification.py --loglevel DEBUG

判断请求成功/失败的推荐方式:
    # 统计所有失败的请求
    sum(aiotest_http_requests_total{assertion_result="fail"}) 目前grafana Failed requests 就是按这个口径统计失败请求数

    # 统计所有成功的请求
    sum(aiotest_http_requests_total{assertion_result="pass"})

    # 断言失败但 HTTP 成功的请求
    sum(aiotest_http_requests_total{assertion_result="fail", status_code=~"2[0-9]{2}"})

    # 断言成功但 HTTP 失败的请求
    sum(aiotest_http_requests_total{assertion_result="pass", status_code=~"[45][0-9]{2}"})

重要提示：
    请始终通过断言来确定被测请求的成功/失败，而不是仅仅记录日志。
    断言的结果会自动反映在 assertion_result 标签中，用于 Prometheus 指标统计。
    这样可以确保请求的成功/失败判断与业务逻辑一致，并且可以通过统一的方式进行监控和分析。

错误计数指标 (ERROR_COUNTER) 说明:
    # 统计所有错误
        - 记录断言失败的信息 ：当请求中的断言失败时，会触发 ERROR_COUNTER 记录
        - 记录其他类型的错误 ：包括网络错误、超时错误、HTTP 错误 ：4xx、5xx 状态码（当这些被断言为失败时）等
        - 提供详细的错误分类 ：通过多个标签提供错误的详细信息
        - 查看接口的响应数据 ：错误消息中包含接口的响应数据，便于调试
    sum(aiotest_errors_total) by (endpoint, error_type, error_message)
"""

import asyncio
import random

from aiotest import ExecutionMode, HttpUser, LoadUserShape, logger


class RequestVerificationUser(HttpUser):
    """请求验证用户类"""
    host = "https://httpbin.org"
    wait_time = (1, 2)
    execution_mode = ExecutionMode.CONCURRENT

    async def test_status_code_success(self):
        """
        测试 HTTP 状态码判断成功

        通过 HTTP 状态码判断请求是否成功：
        - 2xx: 成功
        - 3xx: 重定向
        - 4xx: 客户端错误
        - 5xx: 服务器错误

        注意：当请求成功时，assertion_result 标签会被设置为 "pass"，并记录到 REQUEST_COUNTER 中。
        """
        async with self.client.get("/status/200", name="Status 200 - Success") as resp:
            # 获取响应内容
            data = await resp.text()

            # 验证状态码和响应内容
            assert resp.status == 200, f"预期状态码 200，实际状态码 {resp.status}"

            logger.info(f"请求成功，状态码: {resp.status}，响应内容: {data}")

    async def test_status_code_client_error(self):
        """
        测试 HTTP 4xx 状态码（客户端错误）

        即使 HTTP 状态码是 404，如果断言成功，也会标记为成功

        注意：断言结果是独立于 HTTP 状态码的，只要断言通过，assertion_result 标签就会被设置为 "pass"。
        """
        async with self.client.get("/status/404", name="Status 404 - Not Found") as resp:
            # 获取响应内容
            data = await resp.text()

            # 断言成功，即使状态码是404
            assert resp.status == 404, f"预期状态码 404，实际状态码 {resp.status}"

    async def test_status_code_server_error(self):
        """
        测试 HTTP 5xx 状态码（服务器错误）

        即使 HTTP 状态码是 500，如果断言成功，也会标记为成功

        注意：当断言失败时，assertion_result 标签会被设置为 "fail"，并记录到 ERROR_COUNTER 中。
        """
        async with self.client.get("/status/500", name="Status 500 - Server Error") as resp:
            # 获取响应内容
            data = await resp.text()

            # 断言失败，因为预期状态码是 200，实际是 500
            logger.error(f"请求返回服务器错误，状态码: {resp.status}，响应内容: {data}")
            assert resp.status == 200, f"预期状态码 200，实际状态码 {resp.status}"
            assert data == "success", f"预期响应内容 'success'，实际内容 {data}"

    async def test_response_content_verification(self):
        """
        测试响应内容验证

        验证响应内容是否符合预期

        注意：响应内容验证是确保 API 行为正确性的重要环节，通过验证响应结构和字段值，可以确保业务逻辑的正确性。
        """
        async with self.client.get("/get", name="Response Content Verification") as resp:
            # 验证状态码
            assert resp.status == 200, f"预期状态码 200，实际状态码 {resp.status}"

            # 获取响应内容
            data = await resp.json()

            # 验证响应内容
            assert "headers" in data, "响应中缺少 headers 字段"
            assert "url" in data, "响应中缺少 url 字段"

            logger.info(f"响应内容验证成功，响应数据: {data}")

    async def test_response_time_verification(self):
        """
        测试响应时间验证

        验证响应时间是否在合理范围内

        注意：响应时间是衡量 API 性能的重要指标，通过验证响应时间，可以确保 API 在预期的时间内返回结果。
        """
        import time

        start_time = time.time()
        async with self.client.get("/delay/1", name="Response Time Verification") as resp:
            # 获取响应内容
            data = await resp.json()

            # 计算响应时间
            end_time = time.time()
            response_time = end_time - start_time

            logger.info(f"响应时间: {response_time:.2f} 秒")

            # 验证响应时间是否在合理范围内（不超过 5 秒）
            assert response_time < 5, f"响应时间过长: {response_time:.2f} 秒"
            logger.info("响应时间验证成功")

    async def test_exception_handling(self):
        """
        测试异常处理

        处理请求过程中可能出现的异常

        注意：异常处理是确保测试脚本稳定性的重要环节，通过捕获和处理异常，可以避免测试脚本因单个请求失败而中断。
        """
        try:
            async with self.client.get("/get", name="Exception Handling") as resp:
                # 验证状态码
                assert resp.status == 200, f"预期状态码 200，实际状态码 {resp.status}"

                # 获取响应内容
                data = await resp.json()

                # 验证响应内容
                assert "headers" in data, "响应中缺少 headers 字段"

                logger.info(f"请求成功，响应数据: {data}")
        except Exception as e:
            logger.error(f"请求失败，异常: {e}")
            assert False, f"请求异常: {e}"

    async def test_timeout_handling(self):
        """
        测试超时处理

        处理请求超时的情况

        注意：当请求超时时，异常会在上下文管理器的 __aenter__ 方法中被捕获，
        assertion_result 标签会被正确设置为 "fail"，并记录到 ERROR_COUNTER 中。
        """
        # 设置超时时间为 3 秒
        async with self.client.get("/delay/5", name="Timeout Handling", timeout=3) as resp:
            assert resp.status == 200, f"预期状态码 200，实际状态码 {resp.status}"
            data = await resp.json()

    async def test_retry_mechanism(self):
        """
        测试重试机制

        在请求失败时进行重试

        注意：重试机制可以提高测试的稳定性，特别是在网络不稳定的情况下。通过设置合理的重试次数和间隔，可以减少因临时网络问题导致的测试失败。

        与内置重试机制的区别：
        - 内置重试机制：处理网络级别的错误（如连接错误、超时等），自动重试
        - 手动重试逻辑：可以处理业务级别的错误（如特定状态码），提供更细粒度的控制
        """
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                async with self.client.get("/get", name="Retry Mechanism") as resp:
                    if resp.status == 200:
                        logger.info(f"请求成功，重试次数: {retry_count}")
                        return
                    else:
                        logger.warning(
                            f"请求失败，状态码: {
                                resp.status}，重试次数: {retry_count}")
                        retry_count += 1
                        await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"请求异常: {e}，重试次数: {retry_count}")
                retry_count += 1
                await asyncio.sleep(1)

        logger.error(f"重试 {max_retries} 次后仍然失败")
        assert False, f"重试 {max_retries} 次后仍然失败"

    async def test_error_handling_advanced(self):
        """
        测试高级错误处理

        根据不同的错误类型采取不同的处理方式

        注意：当发生连接错误或超时错误时，异常会在上下文管理器的 __aenter__ 方法中被捕获，
        assertion_result 标签会被正确设置为 "fail"，并记录到 ERROR_COUNTER 中。
        """
        # 测试不同类型的错误

        # 1. 测试连接错误
        try:
            async with self.client.get("/get", name="Connection Test") as resp:
                assert resp.status == 200, f"预期状态码 200，实际状态码 {resp.status}"
                logger.info("连接成功")
        except ConnectionError as e:
            logger.error(f"连接错误: {e}")
            assert False, f"连接错误: {e}"

        # 2. 测试超时错误
        try:
            async with self.client.get("/delay/5", name="Timeout Test", timeout=3) as resp:
                assert resp.status == 200
                logger.info("请求完成")
        except asyncio.TimeoutError:
            logger.error("请求超时")
            assert False, "请求超时"

        # 3. 测试 HTTP 错误
        error_status_codes = [400, 401, 403, 404, 500, 502, 503]
        status_code = random.choice(error_status_codes)

        try:
            async with self.client.get(f"/status/{status_code}", name=f"HTTP Error {status_code}") as resp:
                if 400 <= resp.status < 600:
                    logger.warning(f"HTTP 错误，状态码: {resp.status}")
                    # 根据业务需求决定是否失败
                    # 这里我们断言失败，因为 HTTP 错误通常表示请求失败
                    assert False, f"HTTP 错误，状态码: {resp.status}"
                else:
                    logger.info(f"请求成功，状态码: {resp.status}")
                    assert True
        except Exception as e:
            logger.error(f"请求异常: {e}")
            assert False, f"请求异常: {e}"

    async def test_json_response_validation(self):
        """
        测试 JSON 响应验证

        验证 JSON 响应的结构和内容

        注意：JSON 响应验证是确保 API 返回正确数据结构的重要环节，通过验证 JSON 结构和字段值，可以确保 API 行为符合预期。
        """
        async with self.client.post(
            "/post",
            json={"name": "test", "value": 123},
            name="JSON Response Validation"
        ) as resp:
            # 验证状态码
            assert resp.status == 200, f"预期状态码 200，实际状态码 {resp.status}"

            # 获取 JSON 响应
            data = await resp.json()

            # 验证 JSON 结构
            assert "json" in data, "响应中缺少 json 字段"

            # 验证 JSON 内容
            json_data = data["json"]
            assert json_data["name"] == "test", f"预期 name 为 test，实际为 {
                json_data['name']}"
            assert json_data["value"] == 123, f"预期 value 为 123，实际为 {
                json_data['value']}"

            logger.info(f"JSON 响应验证成功: {json_data}")

    async def test_headers_verification(self):
        """
        测试响应头验证

        验证响应头是否包含必要的字段

        注意：响应头验证是确保 API 返回正确元数据的重要环节，通过验证响应头，可以确保 API 行为符合预期，例如内容类型、缓存控制等。
        """
        async with self.client.get("/get", name="Headers Verification") as resp:
            # 验证状态码
            assert resp.status == 200, f"预期状态码 200，实际状态码 {resp.status}"

            # 获取响应头
            headers = resp.headers

            # 验证响应头
            assert "Content-Type" in headers, "响应头中缺少 Content-Type"
            assert "Date" in headers, "响应头中缺少 Date"

            logger.info(f"响应头验证成功: {dict(headers)}")

            # 验证 Content-Type
            content_type = headers["Content-Type"]
            assert "application/json" in content_type, f"预期 Content-Type 包含 application/json，实际为 {content_type}"

            logger.info("Content-Type 验证成功")

    async def test_assertion_result_label(self):
        """
        测试断言结果标签

        展示断言结果如何影响 Prometheus 指标

        使用以下 Prometheus 查询判断请求成功/失败：
        # 统计所有失败的请求
        sum(aiotest_http_requests_total{assertion_result="fail"})

        # 统计所有成功的请求
        sum(aiotest_http_requests_total{assertion_result="pass"})
        """
        # 测试 1: 断言成功，即使 HTTP 状态码是 400
        async with self.client.get("/status/400", name="Assertion Pass with 400") as resp:
            logger.info(f"测试 1: 状态码 {resp.status}，断言成功")
            # 即使状态码是 400，断言成功也会标记为成功
            assert True

        # 测试 2: 断言失败，即使 HTTP 状态码是 200
        try:
            async with self.client.get("/status/200", name="Assertion Fail with 200") as resp:
                logger.info(f"测试 2: 状态码 {resp.status}，断言失败")
                # 即使状态码是 200，断言失败也会标记为失败
                assert False, "故意的断言失败"
        except AssertionError:
            # 预期的断言失败
            pass


class RequestVerificationLoadShape(LoadUserShape):
    """
    请求验证负载形状

    设计适合请求验证测试的负载形状
    """
    stages = [
        {"duration": 30, "user_count": 2, "rate": 1},  # 0-30秒：2个用户，每秒1个
        {"duration": 60, "user_count": 4, "rate": 2},  # 30-60秒：4个用户，每秒2个
        {"duration": 90, "user_count": 6, "rate": 3},  # 60-90秒：6个用户，每秒3个
        {"duration": 120, "user_count": 10, "rate": 2},  # 90-120秒：10个用户，每秒2个
    ]

    def tick(self):
        """计算当前应该使用的用户数和生成速率"""
        run_time = self.get_run_time()

        for stage in self.stages:
            if run_time < stage["duration"]:
                return (stage["user_count"], stage["rate"])

        return None


# 请求成功/失败判定最佳实践总结
"""
请求成功/失败判定最佳实践：

1. HTTP 状态码判断：
   - 2xx (200-299): 请求成功
   - 3xx (300-399): 重定向，通常也算成功
   - 4xx (400-499): 客户端错误，通常算失败
   - 5xx (500-599): 服务器错误，算失败

2. 响应内容验证：
   - 验证响应 JSON 结构
   - 验证响应字段值
   - 验证响应数据完整性

3. 响应时间验证：
   - 设置合理的超时时间
   - 验证响应时间是否在合理范围内
   - 记录慢请求

4. 异常处理：
   - 使用 try-except 捕获异常
   - 区分不同类型的异常
   - 记录详细的错误日志

5. 超时处理：
   - 设置合理的超时时间
   - 区分连接超时和读取超时
   - 超时后进行重试

6. 重试机制：
   - 设置最大重试次数
   - 使用指数退避算法
   - 记录重试次数

7. 日志记录：
   - 记录请求的详细信息
   - 记录响应的详细信息
   - 记录错误信息

8. 断言使用：
   - 使用有意义的断言消息
   - 验证关键字段
   - 验证业务逻辑

9. 错误分类：
   - 网络错误：连接失败、DNS 错误等
   - 超时错误：连接超时、读取超时
   - HTTP 错误：4xx、5xx 状态码
   - 业务错误：响应内容不符合预期

10. 监控和告警：
    - 监控请求成功率
    - 监控响应时间
    - 设置告警阈值

11. 断言结果标签（新增）：
    - assertion_result="pass": 断言成功，无论 HTTP 状态码如何
    - assertion_result="fail": 断言失败，无论 HTTP 状态码如何
    - 推荐使用以下 Prometheus 查询判断请求成功/失败：
      # 统计所有失败的请求
      sum(aiotest_http_requests_total{assertion_result="fail"})

      # 统计所有成功的请求
      sum(aiotest_http_requests_total{assertion_result="pass"})

      # 断言失败但 HTTP 成功的请求
      sum(aiotest_http_requests_total{assertion_result="fail", status_code=~"2[0-9]{2}"})

      # 断言成功但 HTTP 失败的请求
      sum(aiotest_http_requests_total{assertion_result="pass", status_code=~"[45][0-9]{2}"})

12. 错误计数指标 (ERROR_COUNTER)：
    - 定义：aiotest_errors_total，记录详细的错误信息
    - 标签：error_type, method, endpoint, status_code, error_message
    - 用途：提供更详细的错误分类和统计
    - 与 REQUEST_COUNTER 的关系：
      - REQUEST_COUNTER 记录所有请求（成功和失败），通过 assertion_result 标签区分
      - ERROR_COUNTER 只记录失败的请求，提供更详细的错误信息
      - 两者可以结合使用，REQUEST_COUNTER 用于整体请求成功率统计，ERROR_COUNTER 用于错误分类和分析
    - 推荐查询：
      # 统计所有错误
      sum(aiotest_errors_total) by (endpoint, error_type, error_message)
"""
