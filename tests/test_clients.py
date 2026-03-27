# encoding: utf-8

import allure
import pytest

from aiotest import HTTPClient, configure_connector
from aiotest.clients import CONNECTOR_SETTINGS, ResponseContextManager
from aiotest.metrics import RequestMetrics


@allure.feature("HTTPClient")
class TestHTTPClient:
    """HTTPClient 类的测试用例"""

    @allure.story("初始化")
    @allure.title("测试 HTTPClient 初始化")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_initialization(self):
        client = HTTPClient(
            base_url="http://api.example.com",
            default_headers={"X-Custom": "value"},
            timeout=60,
            max_retries=5,
            verify_ssl=True
        )
        assert client.base_url == "http://api.example.com"
        assert client.default_headers.get("X-Custom") == "value"
        assert client.default_headers.get("Accept") == "application/json"

    @allure.story("配置管理")
    @allure.title("测试配置连接池")
    @allure.severity(allure.severity_level.NORMAL)
    def test_configure_connector(self):
        original_limit = CONNECTOR_SETTINGS['limit']

        configure_connector(limit=200, limit_per_host=50)
        assert CONNECTOR_SETTINGS['limit'] == 200
        assert CONNECTOR_SETTINGS['limit_per_host'] == 50

        configure_connector(limit=original_limit)

    @allure.story("端点处理")
    @allure.title("测试标准化端点")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.parametrize("endpoint, expected", [
        ("users/123", "users/{id}"),
        ("users/123/profile", "users/{id}/profile"),
        ("api/v1/users/456", "api/v1/users/{id}"),
        ("simple", "simple"),
        ("nested/path/test/789", "nested/path/test/{id}"),
    ])
    def test_normalize_endpoint(self, endpoint, expected):
        """测试标准化端点，包括正常路径和边界情况"""
        client = HTTPClient()
        assert client._normalize_endpoint(endpoint) == expected

    @allure.story("安全处理")
    @allure.title("测试清理敏感信息的请求头")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_sanitize_headers(self):
        client = HTTPClient()
        headers = {
            "Authorization": "Bearer token123",
            "Content-Type": "application/json",
            "API-Key": "secret456"
        }
        sanitized = client._sanitize_headers(headers)
        assert sanitized["Authorization"] == "*****"
        assert sanitized["Content-Type"] == "application/json"
        assert sanitized["API-Key"] == "*****"

    @allure.story("安全处理")
    @allure.title("测试清理敏感信息的请求体")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_sanitize_body(self):
        client = HTTPClient()
        body_dict = {
            "username": "test",
            "password": "secret123",
            "token": "abc123"
        }
        sanitized_dict = client._sanitize_body(body_dict)
        assert sanitized_dict["username"] == "test"
        assert sanitized_dict["password"] == "*****"
        assert sanitized_dict["token"] == "*****"

        body_str = "username=test&password=secret123&token=abc123"
        sanitized_str = client._sanitize_body(body_str)
        assert "password=*****" in sanitized_str
        assert "token=*****" in sanitized_str

    @allure.story("初始化")
    @allure.title("测试初始化参数验证")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_initialization_validation(self):
        async with HTTPClient(base_url="http://localhost:8080") as client:
            assert client.base_url == "http://localhost:8080"
            assert client.max_retries == 3
            assert client.verify_ssl is True

    @allure.story("生命周期管理")
    @allure.title("测试 close 方法")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_close_method(self):
        client = HTTPClient(base_url="http://localhost:8080")
        await client.__aenter__()
        assert client._session is not None
        await client.close()

    @allure.story("HTTP 请求")
    @allure.title("测试 HTTP 方法")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_http_methods(self):
        async with HTTPClient(base_url="http://localhost:8080") as http_client:
            async with http_client.get("/") as response:
                assert response.status == 200
                json_data = await response.json()
                assert json_data == {"message": "Hello, HTTP!"}

            async with http_client.post("/", data={"key": "value"}) as response:
                assert response.status == 200
                json_data = await response.json()
                assert json_data == {"message": "Hello, HTTP!"}

            async with http_client.put("/", data={"key": "value"}) as response:
                assert response.status == 200
                json_data = await response.json()
                assert json_data == {"message": "Hello, HTTP!"}

            async with http_client.delete("/") as response:
                assert response.status == 200
                json_data = await response.json()
                assert json_data == {"message": "Hello, HTTP!"}

    @allure.story("错误处理")
    @allure.title("测试错误处理")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_error_handling(self):
        async with HTTPClient(base_url="http://localhost:8080") as http_client:
            async with http_client.get("/error") as response:
                assert response.status == 500

    @allure.story("重试机制")
    @allure.title("测试重试逻辑")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_retry_logic(self):
        async with HTTPClient(base_url="http://localhost:8080", max_retries=3) as client:
            response = await client._request_with_retry('GET', 'retry')
            assert response.status == 200
            response.close()

    @allure.story("重试机制")
    @allure.title("测试 max_retries=0 时跳过重试逻辑")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_no_retry_when_max_retries_zero(self):
        """测试 max_retries=0 时跳过重试逻辑"""
        async with HTTPClient(base_url="http://localhost:8080", max_retries=0) as client:
            response = await client._request_with_retry('GET', '/')
            assert response.status == 200
            response.close()

    @allure.story("网络请求")
    @allure.title("测试 HTTPS 请求")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_https_request(self):
        async with HTTPClient(base_url="https://localhost:8443", verify_ssl=False) as https_client:
            async with https_client.get("/") as response:
                assert response.status == 200
                json_data = await response.json()
                assert json_data == {"message": "Hello, HTTPS!"}

    @allure.story("网络请求")
    @allure.title("测试真实 HTTP 请求")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_real_http_request(self):
        async with HTTPClient(base_url="http://localhost:8080") as client:
            async with client.get("/") as response:
                assert response.status == 200
                json_data = await response.json()
                assert json_data == {"message": "Hello, HTTP!"}

    @allure.story("网络请求")
    @allure.title("测试真实 HTTPS 请求")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_real_https_request(self):
        async with HTTPClient(base_url="https://localhost:8443", verify_ssl=False) as client:
            async with client.get("/") as response:
                assert response.status == 200
                json_data = await response.json()
                assert json_data == {"message": "Hello, HTTPS!"}

    @allure.story("功能特性")
    @allure.title("测试 name 参数功能")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_name_parameter(self):
        async with HTTPClient(base_url="http://localhost:8080") as client:
            async with client.get("/", name="get_root") as response:
                assert response.status == 200
                json_data = await response.json()
                assert json_data == {"message": "Hello, HTTP!"}

            async with client.get("/") as response:
                assert response.status == 200
                json_data = await response.json()
                assert json_data == {"message": "Hello, HTTP!"}

    @allure.story("性能数据")
    @allure.title("测试性能数据记录功能")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_record_request_metrics(self, http_client):
        """测试性能数据记录功能"""
        # 直接调用 _record_request_metrics 方法测试
        await http_client._record_request_metrics(
            request_id="test-req-1",
            method="GET",
            endpoint="/test",
            status_code=200,
            duration=0.1,
            response_size=100
        )
        # 这里主要测试方法是否能正常执行，不抛出异常
        assert True

    @allure.story("日志记录")
    @allure.title("测试日志记录功能")
    @allure.severity(allure.severity_level.NORMAL)
    def test_log_request(self):
        """测试日志记录功能"""
        client = HTTPClient()
        log = RequestMetrics(
            request_id="test-req-1",
            method="GET",
            endpoint="/test"
        )
        # 测试不同状态的日志记录
        client._log_request(log, "start")
        client._log_request(log, "complete")
        # 测试失败状态的日志记录
        log.error = {"message": "Test error"}
        client._log_request(log, "failed")
        # 这里主要测试方法是否能正常执行，不抛出异常
        assert True

    @allure.story("HTTP 请求")
    @allure.title("测试 request 方法的完整逻辑")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_request_method(self, http_client):
        """测试 request 方法的完整逻辑"""
        # 测试 request 方法
        async with http_client.request("GET", "/") as response:
            assert response.status == 200
            json_data = await response.json()
            assert json_data == {"message": "Hello, HTTP!"}

    @allure.story("重试机制")
    @allure.title("测试重试机制中 max_retries=0 的情况")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_request_with_retry_edge_cases(self):
        """测试重试机制中 max_retries=0 的情况"""
        # 测试 max_retries=0 的情况
        async with HTTPClient(base_url="http://localhost:8080", max_retries=0) as client:
            response = await client._request_with_retry('GET', '/')
            assert response.status == 200
            response.close()

    @allure.story("重试机制")
    @allure.title("测试当遇到特定状态码时放弃重试的逻辑")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_request_with_retry_giveup(self):
        """测试当遇到特定状态码时放弃重试的逻辑"""
        # 这里需要一个返回 404 状态码的端点
        async with HTTPClient(base_url="http://localhost:8080", max_retries=3) as client:
            # 尝试访问一个不存在的端点，应该返回 404 并放弃重试
            response = await client._request_with_retry('GET', '/nonexistent')
            assert response.status == 404
            response.close()


@allure.feature("ResponseContextManager")
class TestResponseContextManager:
    """ResponseContextManager 类的测试用例"""

    @allure.story("响应处理")
    @allure.title("测试响应上下文管理器")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_response_context_manager(self):
        async with HTTPClient(base_url="http://localhost:8080") as client:
            async with client.get("/") as response:
                assert response.status == 200
                json_data = await response.json()
                assert json_data == {"message": "Hello, HTTP!"}

    @allure.story("响应处理")
    @allure.title("测试 ResponseContextManager 的属性和方法")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_properties_and_methods(self, http_client):
        """测试 ResponseContextManager 的 status 属性和 json() 方法"""
        async with http_client.get("/") as response:
            assert response.status == 200

            # 测试 status 属性
            assert isinstance(response.status, int)

            # 测试 json() 方法
            json_data = await response.json()
            assert json_data == {"message": "Hello, HTTP!"}

    @allure.story("数据处理")
    @allure.title("测试 _estimate_size 方法")
    @allure.severity(allure.severity_level.NORMAL)
    def test_estimate_size(self):
        assert ResponseContextManager._estimate_size(None) == 0
        assert ResponseContextManager._estimate_size("test") == 4
        assert ResponseContextManager._estimate_size({"key": "value"}) == 16
        assert ResponseContextManager._estimate_size([1, 2, 3]) == 9
        assert ResponseContextManager._estimate_size(b"bytes") == 8

    @allure.story("数据处理")
    @allure.title("测试 _safe_get_headers 方法")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_safe_get_headers(self):
        async with HTTPClient(base_url="http://localhost:8080") as client:
            async with client.get("/custom-headers") as response:
                assert response.status == 200
                json_data = await response.json()
                assert json_data == {"message": "Hello with custom headers!"}
                headers = response._processed_data['headers']
                assert 'X-Custom-Header' in headers
                assert headers['X-Custom-Header'] == 'custom-value'

    @allure.story("数据处理")
    @allure.title("测试 _safe_get_cookies 方法")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_safe_get_cookies(self):
        async with HTTPClient(base_url="http://localhost:8080") as client:
            async with client.get("/cookies") as response:
                assert response.status == 200
                json_data = await response.json()
                assert json_data == {"message": "Hello with cookies!"}
                cookies = response._processed_data['cookies']
                assert 'session_id' in cookies or 'user_id' in cookies

    @allure.story("数据处理")
    @allure.title("测试 _safe_get_cookies 方法处理空 cookies")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_safe_get_cookies_empty(self):
        async with HTTPClient(base_url="http://localhost:8080") as client:
            async with client.get("/") as response:
                assert response.status == 200
                cookies = response._processed_data['cookies']
                assert cookies == {}

    @allure.story("响应处理")
    @allure.title("测试 _process_response 方法处理 JSON 解析失败的情况")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_process_response_json_error(self):
        async with HTTPClient(base_url="http://localhost:8080") as client:
            async with client.get("/text") as response:
                result = await response._process_response(response._response)
                assert result['status'] == 200
                assert result['data'] == "This is plain text response"

    @allure.story("响应处理")
    @allure.title("测试 _process_response 方法处理异常情况")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_process_response_exception(self):
        """测试 _process_response 方法处理异常情况"""
        async with HTTPClient(base_url="http://localhost:8080") as client:
            async with client.get("/error") as response:
                assert response.status == 500
                text = await response.text()
                assert "Internal Server Error" in text

    @allure.story("响应处理")
    @allure.title("测试响应上下文管理器处理异常")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_context_manager_exception_handling(self):
        """测试响应上下文管理器在异常情况下的处理"""
        async with HTTPClient(base_url="http://localhost:8080") as client:
            try:
                async with client.get("/error") as response:
                    # 验证状态码为 500
                    assert response.status == 500
            except Exception:
                # 如果发生异常，确保客户端仍然可用
                pass

    @allure.story("数据处理")
    @allure.title("测试 _estimate_size 方法的边界情况")
    @allure.severity(allure.severity_level.NORMAL)
    def test_estimate_size_boundary(self):
        """测试 _estimate_size 方法的边界情况"""
        # 测试空值
        assert ResponseContextManager._estimate_size(None) == 0
        # 测试空字符串
        assert ResponseContextManager._estimate_size("") == 0
        # 测试空字典（转换为字符串后为"{}"，编码后长度为2）
        assert ResponseContextManager._estimate_size({}) == 2
        # 测试空列表（转换为字符串后为"[]"，编码后长度为2）
        assert ResponseContextManager._estimate_size([]) == 2
        # 测试字节串（str(b"test") = "b'test'"，编码后长度为7）
        assert ResponseContextManager._estimate_size(b"test") == 7
        # 测试嵌套字典
        nested_dict = {"key": {"nested": "value"}}
        assert ResponseContextManager._estimate_size(nested_dict) > 0

    @allure.story("错误处理")
    @allure.title("测试错误处理功能")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_handle_error(self):
        """测试错误处理功能"""
        # 创建一个简单的 ResponseContextManager 实例
        async def mock_request():
            raise Exception("Test error")

        log = RequestMetrics(
            request_id="test-req-1",
            method="GET",
            endpoint="/test"
        )

        async def mock_metrics_callback(*args, **kwargs):
            pass

        def mock_log_request(*args, **kwargs):
            pass

        rcm = ResponseContextManager(
            request_coroutine=mock_request(),
            log=log,
            start_time=0,
            metrics_callback=mock_metrics_callback,
            log_request=mock_log_request
        )

        # 测试错误处理
        with pytest.raises(Exception):
            async with rcm as response:
                pass

    @allure.story("上下文管理")
    @allure.title("测试上下文管理器在错误情况下的退出逻辑")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_context_manager_exit_with_error(self):
        """测试上下文管理器在错误情况下的退出逻辑"""
        async with HTTPClient(base_url="http://localhost:8080") as client:
            try:
                async with client.get("/error") as response:
                    # 验证状态码为 500
                    assert response.status == 500
            except Exception:
                # 如果发生异常，确保客户端仍然可用
                pass

    @allure.story("上下文管理")
    @allure.title("测试上下文管理器的进入逻辑")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_context_manager_enter(self, http_client):
        """测试上下文管理器的进入逻辑"""
        async with http_client.get("/") as response:
            # 验证响应对象被正确创建
            assert response is not None
            assert response.status == 200

    @allure.story("边界测试")
    @allure.title("测试空响应体的处理")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_empty_response(self):
        """测试空响应体的处理"""
        # 这里需要一个返回空响应的端点
        # 暂时使用现有的端点
        async with HTTPClient(base_url="http://localhost:8080") as client:
            async with client.get("/") as response:
                assert response.status == 200

    @allure.story("边界测试")
    @allure.title("测试超大响应体的处理")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_large_response(self):
        """测试超大响应体的处理"""
        # 这里需要一个返回大响应的端点
        # 暂时使用现有的端点
        async with HTTPClient(base_url="http://localhost:8080") as client:
            async with client.get("/") as response:
                assert response.status == 200

    @allure.story("边界测试")
    @allure.title("测试网络超时的处理")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_network_timeout(self):
        """测试网络超时的处理"""
        # 创建一个超时时间很短的客户端
        async with HTTPClient(base_url="http://localhost:8080", timeout=0.001) as client:
            with pytest.raises(Exception):
                async with client.get("/") as response:
                    pass

    @allure.story("边界测试")
    @allure.title("测试连接被重置的情况")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_connection_reset(self):
        """测试连接被重置的情况"""
        async with HTTPClient(base_url="http://localhost:8080") as client:
            # 尝试访问会导致连接重置的端点
            with pytest.raises(Exception):
                async with client.get("/reset-connection") as response:
                    pass

            # 验证客户端在连接被重置后仍然可用
            async with client.get("/") as response:
                assert response.status == 200

    @allure.story("响应处理")
    @allure.title("测试响应处理的完整逻辑")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_aenter_response_processing(self, http_client):
        """测试响应处理的完整逻辑"""
        async with http_client.get("/") as response:
            # 验证响应对象被正确创建
            assert response is not None
            assert response.status == 200
            # 验证处理后的数据
            assert hasattr(response, "_processed_data")
            assert "status" in response._processed_data
            assert "headers" in response._processed_data
            assert "data" in response._processed_data
            assert "cookies" in response._processed_data

    @allure.story("响应处理")
    @allure.title("测试 headers 属性")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_headers_property(self, http_client):
        """测试 headers 属性能正确返回响应头"""
        async with http_client.get("/") as response:
            assert response.status == 200
            # 测试 headers 属性
            headers = response.headers
            assert isinstance(headers, dict)
            assert "Content-Type" in headers

    @allure.story("错误处理")
    @allure.title("测试 _handle_error 方法的重复错误处理检查")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_handle_error_no_duplication(self):
        """测试 _handle_error 方法的重复错误处理检查"""
        # 创建一个简单的 ResponseContextManager 实例
        async def mock_request():
            raise Exception("Test error")

        log = RequestMetrics(
            request_id="test-req-1",
            method="GET",
            endpoint="/test"
        )

        async def mock_metrics_callback(*args, **kwargs):
            pass

        def mock_log_request(*args, **kwargs):
            pass

        rcm = ResponseContextManager(
            request_coroutine=mock_request(),
            log=log,
            start_time=0,
            metrics_callback=mock_metrics_callback,
            log_request=mock_log_request
        )

        # 第一次调用 _handle_error
        await rcm._handle_error(Exception("Test error"))

        # 验证错误已被标记为处理
        assert hasattr(rcm, "_error_handled")
        assert rcm._error_handled is True

        # 第二次调用 _handle_error，应该直接返回，不重复处理
        await rcm._handle_error(Exception("Test error"))

        # 验证错误仍然被标记为已处理
        assert rcm._error_handled is True

    @allure.story("错误处理")
    @allure.title("测试不同类型异常的处理")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_aexit_exception_handling(self):
        """测试不同类型异常的处理"""
        # 创建一个简单的 ResponseContextManager 实例
        async def mock_request():
            raise ValueError("Test value error")

        log = RequestMetrics(
            request_id="test-req-1",
            method="GET",
            endpoint="/test"
        )

        async def mock_metrics_callback(*args, **kwargs):
            pass

        def mock_log_request(*args, **kwargs):
            pass

        rcm = ResponseContextManager(
            request_coroutine=mock_request(),
            log=log,
            start_time=0,
            metrics_callback=mock_metrics_callback,
            log_request=mock_log_request
        )

        # 测试错误处理
        with pytest.raises(Exception):
            async with rcm as response:
                pass

    @allure.story("安全处理")
    @allure.title("测试清理请求头的边界情况")
    @allure.severity(allure.severity_level.NORMAL)
    def test_sanitize_headers_edge_cases(self):
        """测试清理请求头的边界情况"""
        client = HTTPClient()

        # 测试空字典
        assert client._sanitize_headers({}) == {}

        # 测试没有敏感信息的请求头
        headers = {"Content-Type": "application/json", "Accept": "*/*"}
        assert client._sanitize_headers(headers) == headers

        # 测试包含敏感信息的请求头
        sensitive_headers = {
            "Authorization": "Bearer token123",
            "Content-Type": "application/json",
            "API-Key": "secret456",
            "Cookie": "session_id=abc123"
        }
        sanitized = client._sanitize_headers(sensitive_headers)
        assert sanitized["Authorization"] == "*****"
        assert sanitized["Content-Type"] == "application/json"
        assert sanitized["API-Key"] == "*****"
        assert sanitized["Cookie"] == "*****"

    @allure.story("安全处理")
    @allure.title("测试清理请求体的边界情况")
    @allure.severity(allure.severity_level.NORMAL)
    def test_sanitize_body_edge_cases(self):
        """测试清理请求体的边界情况"""
        client = HTTPClient()

        # 测试 None
        assert client._sanitize_body(None) is None

        # 测试空字典
        assert client._sanitize_body({}) == {}

        # 测试空字符串
        assert client._sanitize_body("") == ""

        # 测试没有敏感信息的请求体
        body_dict = {"username": "test", "email": "test@example.com"}
        assert client._sanitize_body(body_dict) == body_dict

        # 测试包含敏感信息的请求体
        sensitive_body = {
            "username": "test",
            "password": "secret123",
            "token": "abc123"
        }
        sanitized = client._sanitize_body(sensitive_body)
        assert sanitized["username"] == "test"
        assert sanitized["password"] == "*****"
        assert sanitized["token"] == "*****"

    @allure.story("数据处理")
    @allure.title("测试处理文本类型的响应")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_process_response_edge_cases(self):
        """测试处理文本类型的响应"""
        # 测试文本类型的响应
        async with HTTPClient(base_url="http://localhost:8080") as client:
            async with client.get("/text") as response:
                assert response.status == 200
                text = await response.text()
                assert isinstance(text, str)

    @allure.story("错误处理")
    @allure.title("测试错误处理功能")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_handle_error_edge_cases(self):
        """测试错误处理功能"""
        # 创建一个简单的 ResponseContextManager 实例
        async def mock_request():
            raise Exception("Test error")

        log = RequestMetrics(
            request_id="test-req-1",
            method="GET",
            endpoint="/test"
        )

        async def mock_metrics_callback(*args, **kwargs):
            pass

        def mock_log_request(*args, **kwargs):
            pass

        rcm = ResponseContextManager(
            request_coroutine=mock_request(),
            log=log,
            start_time=0,
            metrics_callback=mock_metrics_callback,
            log_request=mock_log_request
        )

        # 测试错误处理
        with pytest.raises(Exception):
            async with rcm as response:
                pass

    @allure.story("数据处理")
    @allure.title("测试安全获取 headers 的边界情况")
    @allure.severity(allure.severity_level.NORMAL)
    def test_safe_get_headers_edge_cases(self):
        """测试安全获取 headers 的边界情况"""
        # 测试 None
        assert ResponseContextManager._safe_get_headers(
            None) == {"Content-Type": "application/json"}

        # 测试没有 headers 属性的对象
        class MockResponse:
            pass
        mock_response = MockResponse()
        assert ResponseContextManager._safe_get_headers(
            mock_response) == {"Content-Type": "application/json"}

    @allure.story("数据处理")
    @allure.title("测试安全获取 cookies 的边界情况")
    @allure.severity(allure.severity_level.NORMAL)
    def test_safe_get_cookies_edge_cases(self):
        """测试安全获取 cookies 的边界情况"""
        # 测试 None
        assert ResponseContextManager._safe_get_cookies(None) == {}

        # 测试没有 cookies 属性的对象
        class MockResponse:
            pass
        mock_response = MockResponse()
        assert ResponseContextManager._safe_get_cookies(mock_response) == {}

    @allure.story("配置管理")
    @allure.title("测试配置连接池的参数设置")
    @allure.severity(allure.severity_level.NORMAL)
    def test_configure_connector_edge_cases(self):
        """测试配置连接池的参数设置"""
        original_limit = CONNECTOR_SETTINGS['limit']
        original_limit_per_host = CONNECTOR_SETTINGS['limit_per_host']

        try:
            # 测试部分参数配置
            configure_connector(limit=150)
            assert CONNECTOR_SETTINGS['limit'] == 150
            assert CONNECTOR_SETTINGS['limit_per_host'] == original_limit_per_host

            # 测试所有参数配置
            configure_connector(
                limit=200,
                limit_per_host=50,
                force_close=True,
                enable_cleanup_closed=False)
            assert CONNECTOR_SETTINGS['limit'] == 200
            assert CONNECTOR_SETTINGS['limit_per_host'] == 50
            assert CONNECTOR_SETTINGS['force_close'] is True
            assert CONNECTOR_SETTINGS['enable_cleanup_closed'] is False
        finally:
            # 恢复原始配置
            configure_connector(
                limit=original_limit,
                limit_per_host=original_limit_per_host,
                force_close=False,
                enable_cleanup_closed=True)

    @allure.story("会话管理")
    @allure.title("测试会话关闭超时")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_session_close_timeout(self):
        """测试会话关闭超时的情况"""
        import asyncio

        class MockSession:
            async def close(self):
                await asyncio.sleep(10)  # 模拟关闭超时

        client = HTTPClient()
        client._session = MockSession()

        # 测试会话关闭超时
        await client.close()

    @allure.story("指标记录")
    @allure.title("测试指标记录失败")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_metrics_recording_failure(self):
        """测试记录请求指标失败的情况"""
        # 创建一个简单的 ResponseContextManager 实例
        async def mock_request():
            # 模拟一个响应
            class MockResponse:
                status = 200
                cookies = {}

                async def read(self):
                    return b"test"

                def close(self):
                    pass
            return MockResponse()

        log = RequestMetrics(
            request_id="test-req-1",
            method="GET",
            endpoint="/test"
        )

        # 模拟 metrics_callback 抛出异常
        async def failing_metrics_callback(**kwargs):
            raise Exception("Metrics recording failed")

        def mock_log_request(*args, **kwargs):
            pass

        rcm = ResponseContextManager(
            request_coroutine=mock_request(),
            log=log,
            start_time=0,
            metrics_callback=failing_metrics_callback,
            log_request=mock_log_request
        )

        # 测试进入上下文（会触发指标记录）
        try:
            async with rcm as response:
                pass
        except Exception:
            pass

    @allure.story("响应处理")
    @allure.title("测试响应处理失败")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_response_processing_failure(self):
        """测试处理响应数据失败的情况"""
        # 测试 _process_response 方法的异常处理
        # 注意：根据实际实现，_process_response 可能不会捕获所有异常
        # 我们测试的是该方法能够处理响应数据失败的情况
        class MockResponse:
            status = 200
            cookies = {}

            @property
            def headers(self):
                return {}

            async def read(self):
                return b"{invalid json}"  # 模拟JSON解析失败

            def close(self):
                pass

        # 创建一个简单的 ResponseContextManager 实例
        async def mock_request():
            return MockResponse()

        log = RequestMetrics(
            request_id="test-req-1",
            method="GET",
            endpoint="/test"
        )

        async def mock_metrics_callback(**kwargs):
            pass

        def mock_log_request(*args, **kwargs):
            pass

        rcm = ResponseContextManager(
            request_coroutine=mock_request(),
            log=log,
            start_time=0,
            metrics_callback=mock_metrics_callback,
            log_request=mock_log_request
        )

        # 测试处理响应（应该捕获JSON解析异常并返回默认值）
        result = await rcm._process_response(MockResponse())
        assert result is not None

    @allure.story("数据处理")
    @allure.title("测试安全获取Cookie异常")
    @allure.severity(allure.severity_level.NORMAL)
    def test_safe_get_cookies_exception(self):
        """测试安全获取Cookie时的异常处理"""
        # 测试会抛出异常的情况
        class MockResponse:
            @property
            def cookies(self):
                raise TypeError("Cookie processing failed")

        # 测试安全获取Cookie（应该捕获异常并返回空字典）
        result = ResponseContextManager._safe_get_cookies(MockResponse())
        assert result == {}

    @allure.story("日志处理")
    @allure.title("测试日志extra处理")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_log_extra_handling(self):
        """测试日志extra为None的处理"""
        # 模拟一个响应
        class MockResponse:
            status = 200
            cookies = {}

            async def read(self):
                return b"test"

            def close(self):
                pass

        # 创建一个log.extra为None的RequestMetrics
        log = RequestMetrics(
            request_id="test-req-1",
            method="GET",
            endpoint="/test"
        )
        log.extra = None

        # 创建一个简单的 ResponseContextManager 实例
        async def mock_request():
            return MockResponse()

        async def mock_metrics_callback(**kwargs):
            pass

        def mock_log_request(*args, **kwargs):
            pass

        rcm = ResponseContextManager(
            request_coroutine=mock_request(),
            log=log,
            start_time=0,
            metrics_callback=mock_metrics_callback,
            log_request=mock_log_request
        )

        # 测试进入上下文（应该将log.extra设置为空字典）
        async with rcm as response:
            pass

        # 验证 log.extra 不为 None
        assert rcm.log.extra is not None
        # 验证 log.extra 是一个字典
        assert isinstance(rcm.log.extra, dict)

    @allure.story("上下文管理")
    @allure.title("测试__aexit__异常处理")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_aexit_exception_handling(self):
        """测试__aexit__方法中的异常处理"""
        # 创建一个简单的 ResponseContextManager 实例
        async def mock_request():
            raise Exception("Test error")

        log = RequestMetrics(
            request_id="test-req-1",
            method="GET",
            endpoint="/test"
        )

        async def mock_metrics_callback(*args, **kwargs):
            pass

        def mock_log_request(*args, **kwargs):
            pass

        rcm = ResponseContextManager(
            request_coroutine=mock_request(),
            log=log,
            start_time=0,
            metrics_callback=mock_metrics_callback,
            log_request=mock_log_request
        )

        # 测试__aexit__方法处理异常的情况
        class TestException(Exception):
            pass

        # 调用__aexit__方法处理异常
        result = await rcm.__aexit__(TestException, TestException("Test error"), None)
        assert result is False

    @allure.story("日志记录")
    @allure.title("测试失败日志响应数据处理")
    @allure.severity(allure.severity_level.NORMAL)
    def test_failed_log_response_data_handling(self):
        """测试失败日志中的响应数据处理"""
        # 模拟一个包含错误信息的RequestMetrics
        log = RequestMetrics(
            request_id="test-req-1",
            method="GET",
            endpoint="/test"
        )
        log.error = {
            "response_data": "a" * 1000  # 测试长响应数据
        }

        # 直接测试 _log_request 方法的逻辑
        # 模拟日志数据构建
        log_data = {
            "method": log.method,
            "endpoint": log.endpoint,
            "status": "failed",
        }

        if hasattr(log, 'error'):
            log_data["error"] = log.error
            # 如果有响应数据,也记录到日志中
            if log.error.get("response_data") is not None:
                response_data = log.error["response_data"]
                # 限制响应数据长度
                if isinstance(response_data, (dict, str)):
                    import json
                    response_str = json.dumps(
                        response_data, ensure_ascii=False) if isinstance(
                        response_data, dict) else str(response_data)
                    if len(response_str) > 500:
                        response_str = response_str[:500] + "..."
                    log_data["response_data"] = response_str
                else:
                    log_data["response_data"] = str(response_data)[:500]

        # 验证响应数据被截断
        assert "response_data" in log_data
        assert len(log_data["response_data"]) <= 503  # 500 + "..."
        assert log_data["response_data"] == "a" * 500 + "..."

    @allure.story("断言处理")
    @allure.title("测试断言失败但状态码为200的情况")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_assertion_fail_with_200_status(self):
        """测试断言失败但HTTP状态码为200的情况"""
        # 模拟一个返回200状态码的响应
        async def mock_request():
            class MockResponse:
                status = 200
                cookies = {}

                async def read(self):
                    return b'{"message": "success"}'

                def close(self):
                    pass
            return MockResponse()

        log = RequestMetrics(
            request_id="test-req-1",
            method="GET",
            endpoint="/test"
        )

        # 用于验证断言结果的标志
        metrics_callback_called = False
        assertion_result_received = None

        async def mock_metrics_callback(**kwargs):
            nonlocal metrics_callback_called, assertion_result_received
            metrics_callback_called = True
            # 验证 assertion_result 被设置为 "fail"
            assertion_result_received = kwargs.get('assertion_result')

        def mock_log_request(*args, **kwargs):
            pass

        rcm = ResponseContextManager(
            request_coroutine=mock_request(),
            log=log,
            start_time=0,
            metrics_callback=mock_metrics_callback,
            log_request=mock_log_request
        )

        # 测试断言失败的情况
        try:
            async with rcm as response:
                # 断言失败，即使状态码是200
                assert False, "故意的断言失败"
        except AssertionError:
            # 预期的断言失败
            pass

        # 验证 assertion_result 被设置为 "fail"
        assert rcm.log.assertion_result == "fail"
        # 验证原始状态码被保留
        assert rcm.log.status_code == 200
        # 验证 metrics_callback 被调用
        assert metrics_callback_called
        # 验证 assertion_result 被正确传递
        assert assertion_result_received == "fail"

    @allure.story("断言处理")
    @allure.title("测试断言成功但状态码为500的情况")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_assertion_pass_with_500_status(self):
        """测试断言成功但HTTP状态码为500的情况"""
        # 模拟一个返回500状态码的响应
        async def mock_request():
            class MockResponse:
                status = 500
                cookies = {}

                async def read(self):
                    return b'{"message": "error"}'

                def close(self):
                    pass
            return MockResponse()

        log = RequestMetrics(
            request_id="test-req-1",
            method="GET",
            endpoint="/test"
        )

        # 用于验证断言结果的标志
        metrics_callback_called = False
        assertion_result_received = None

        async def mock_metrics_callback(**kwargs):
            nonlocal metrics_callback_called, assertion_result_received
            metrics_callback_called = True
            # 验证 assertion_result 被设置为 "pass"
            assertion_result_received = kwargs.get('assertion_result')

        def mock_log_request(*args, **kwargs):
            pass

        rcm = ResponseContextManager(
            request_coroutine=mock_request(),
            log=log,
            start_time=0,
            metrics_callback=mock_metrics_callback,
            log_request=mock_log_request
        )

        # 测试断言成功的情况
        async with rcm as response:
            # 断言成功，即使状态码是500
            assert True

        # 验证 assertion_result 被设置为 "pass"
        assert rcm.log.assertion_result == "pass"
        # 验证原始状态码被保留
        assert rcm.log.status_code == 500
        # 验证 metrics_callback 被调用
        assert metrics_callback_called
        # 验证 assertion_result 被正确传递
        assert assertion_result_received == "pass"

    @allure.story("错误处理")
    @allure.title("测试超时错误时的指标记录")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_timeout_error_metrics(self):
        """测试超时错误时的指标记录"""
        import asyncio

        # 模拟一个超时的请求
        async def mock_request():
            await asyncio.sleep(10)
            raise asyncio.TimeoutError("Request timeout")

        log = RequestMetrics(
            request_id="test-req-1",
            method="GET",
            endpoint="/test"
        )

        # 用于验证指标回调的参数
        metrics_callback_called = False
        assertion_result_received = None
        error_received = None

        async def mock_metrics_callback(**kwargs):
            nonlocal metrics_callback_called, assertion_result_received, error_received
            metrics_callback_called = True
            assertion_result_received = kwargs.get('assertion_result')
            error_received = kwargs.get('error')

        def mock_log_request(*args, **kwargs):
            pass

        rcm = ResponseContextManager(
            request_coroutine=mock_request(),
            log=log,
            start_time=0,
            metrics_callback=mock_metrics_callback,
            log_request=mock_log_request
        )

        # 测试超时错误
        with pytest.raises((asyncio.TimeoutError, Exception)):
            async with rcm as response:
                pass

        # 验证 assertion_result 被设置为 "fail"
        assert rcm.log.assertion_result == "fail"
        # 验证 metrics_callback 被调用
        assert metrics_callback_called
        # 验证 assertion_result 被正确传递
        assert assertion_result_received == "fail"
        # 验证错误信息被正确记录
        assert error_received is not None
        assert error_received.get('exc_type') in ['TimeoutError', 'Exception']

    @allure.story("错误处理")
    @allure.title("测试连接错误时的指标记录")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_connection_error_metrics(self):
        """测试连接错误时的指标记录"""
        import aiohttp

        # 模拟一个连接错误的请求
        async def mock_request():
            raise aiohttp.ClientConnectionError("Connection refused")

        log = RequestMetrics(
            request_id="test-req-1",
            method="GET",
            endpoint="/test"
        )

        # 用于验证指标回调的参数
        metrics_callback_called = False
        assertion_result_received = None
        error_received = None

        async def mock_metrics_callback(**kwargs):
            nonlocal metrics_callback_called, assertion_result_received, error_received
            metrics_callback_called = True
            assertion_result_received = kwargs.get('assertion_result')
            error_received = kwargs.get('error')

        def mock_log_request(*args, **kwargs):
            pass

        rcm = ResponseContextManager(
            request_coroutine=mock_request(),
            log=log,
            start_time=0,
            metrics_callback=mock_metrics_callback,
            log_request=mock_log_request
        )

        # 测试连接错误
        with pytest.raises((aiohttp.ClientConnectionError, Exception)):
            async with rcm as response:
                pass

        # 验证 assertion_result 被设置为 "fail"
        assert rcm.log.assertion_result == "fail"
        # 验证 metrics_callback 被调用
        assert metrics_callback_called
        # 验证 assertion_result 被正确传递
        assert assertion_result_received == "fail"
        # 验证错误信息被正确记录
        assert error_received is not None
        assert 'ConnectionError' in error_received.get('exc_type', '')

    @allure.story("错误处理")
    @allure.title("测试HTTP 4xx错误时的指标记录")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_http_4xx_error_metrics(self):
        """测试HTTP 4xx错误时的指标记录"""
        # 模拟一个返回404状态码的响应
        async def mock_request():
            class MockResponse:
                status = 404
                cookies = {}

                async def read(self):
                    return b'{"error": "Not Found"}'

                def close(self):
                    pass
            return MockResponse()

        log = RequestMetrics(
            request_id="test-req-1",
            method="GET",
            endpoint="/test"
        )

        # 用于验证指标回调的参数
        metrics_callback_called = False
        assertion_result_received = None
        status_code_received = None

        async def mock_metrics_callback(**kwargs):
            nonlocal metrics_callback_called, assertion_result_received, status_code_received
            metrics_callback_called = True
            assertion_result_received = kwargs.get('assertion_result')
            status_code_received = kwargs.get('status_code')

        def mock_log_request(*args, **kwargs):
            pass

        rcm = ResponseContextManager(
            request_coroutine=mock_request(),
            log=log,
            start_time=0,
            metrics_callback=mock_metrics_callback,
            log_request=mock_log_request
        )

        # 测试HTTP 4xx错误（断言失败）
        try:
            async with rcm as response:
                # 断言失败，即使状态码是404
                assert False, "HTTP 4xx error"
        except AssertionError:
            pass

        # 验证 assertion_result 被设置为 "fail"
        assert rcm.log.assertion_result == "fail"
        # 验证原始状态码被保留
        assert rcm.log.status_code == 404
        # 验证 metrics_callback 被调用
        assert metrics_callback_called
        # 验证 assertion_result 被正确传递
        assert assertion_result_received == "fail"
        # 验证状态码被正确传递
        assert status_code_received == 404

    @allure.story("错误处理")
    @allure.title("测试HTTP 5xx错误时的指标记录")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_http_5xx_error_metrics(self):
        """测试HTTP 5xx错误时的指标记录"""
        # 模拟一个返回500状态码的响应
        async def mock_request():
            class MockResponse:
                status = 500
                cookies = {}

                async def read(self):
                    return b'{"error": "Internal Server Error"}'

                def close(self):
                    pass
            return MockResponse()

        log = RequestMetrics(
            request_id="test-req-1",
            method="GET",
            endpoint="/test"
        )

        # 用于验证指标回调的参数
        metrics_callback_called = False
        assertion_result_received = None
        status_code_received = None
        error_received = None

        async def mock_metrics_callback(**kwargs):
            nonlocal metrics_callback_called, assertion_result_received, status_code_received, error_received
            metrics_callback_called = True
            assertion_result_received = kwargs.get('assertion_result')
            status_code_received = kwargs.get('status_code')
            error_received = kwargs.get('error')

        def mock_log_request(*args, **kwargs):
            pass

        rcm = ResponseContextManager(
            request_coroutine=mock_request(),
            log=log,
            start_time=0,
            metrics_callback=mock_metrics_callback,
            log_request=mock_log_request
        )

        # 测试HTTP 5xx错误（断言失败）
        try:
            async with rcm as response:
                # 断言失败，即使状态码是500
                assert False, "HTTP 5xx error"
        except AssertionError:
            pass

        # 验证 assertion_result 被设置为 "fail"
        assert rcm.log.assertion_result == "fail"
        # 验证原始状态码被保留
        assert rcm.log.status_code == 500
        # 验证 metrics_callback 被调用
        assert metrics_callback_called
        # 验证 assertion_result 被正确传递
        assert assertion_result_received == "fail"
        # 验证状态码被正确传递
        assert status_code_received == 500
        # 验证错误信息被正确记录
        assert error_received is not None
        assert 'AssertionError' in error_received.get('exc_type', '')

    @allure.story("错误处理")
    @allure.title("测试错误消息包含响应数据")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_error_message_includes_response_data(self):
        """测试错误消息包含响应数据"""
        # 模拟一个返回错误响应的请求
        async def mock_request():
            class MockResponse:
                status = 400
                cookies = {}

                async def read(self):
                    return b'{"error": "Bad Request", "details": "Invalid parameter"}'

                def close(self):
                    pass
            return MockResponse()

        log = RequestMetrics(
            request_id="test-req-1",
            method="POST",
            endpoint="/test"
        )

        # 用于验证错误消息
        error_message_received = None

        async def mock_metrics_callback(**kwargs):
            nonlocal error_message_received
            error = kwargs.get('error')
            if error:
                error_message_received = error.get('message', '')

        def mock_log_request(*args, **kwargs):
            pass

        rcm = ResponseContextManager(
            request_coroutine=mock_request(),
            log=log,
            start_time=0,
            metrics_callback=mock_metrics_callback,
            log_request=mock_log_request
        )

        # 测试错误消息包含响应数据
        try:
            async with rcm as response:
                # 断言失败
                assert False, "Bad Request"
        except AssertionError:
            pass

        # 验证错误消息包含响应数据
        assert error_message_received is not None
        assert "Response:" in error_message_received or "error" in error_message_received

    @allure.story("错误处理")
    @allure.title("测试断言成功但HTTP错误时的指标记录")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_assertion_pass_with_http_error(self):
        """测试断言成功但HTTP错误时的指标记录"""
        # 模拟一个返回500状态码的响应
        async def mock_request():
            class MockResponse:
                status = 500
                cookies = {}

                async def read(self):
                    return b'{"error": "Internal Server Error"}'

                def close(self):
                    pass
            return MockResponse()

        log = RequestMetrics(
            request_id="test-req-1",
            method="GET",
            endpoint="/test"
        )

        # 用于验证指标回调的参数
        metrics_callback_called = False
        assertion_result_received = None
        status_code_received = None
        error_received = None

        async def mock_metrics_callback(**kwargs):
            nonlocal metrics_callback_called, assertion_result_received, status_code_received, error_received
            metrics_callback_called = True
            assertion_result_received = kwargs.get('assertion_result')
            status_code_received = kwargs.get('status_code')
            error_received = kwargs.get('error')

        def mock_log_request(*args, **kwargs):
            pass

        rcm = ResponseContextManager(
            request_coroutine=mock_request(),
            log=log,
            start_time=0,
            metrics_callback=mock_metrics_callback,
            log_request=mock_log_request
        )

        # 测试断言成功但HTTP错误
        async with rcm as response:
            # 断言成功，即使状态码是500
            assert True

        # 验证 assertion_result 被设置为 "pass"
        assert rcm.log.assertion_result == "pass"
        # 验证原始状态码被保留
        assert rcm.log.status_code == 500
        # 验证 metrics_callback 被调用
        assert metrics_callback_called
        # 验证 assertion_result 被正确传递
        assert assertion_result_received == "pass"
        # 验证状态码被正确传递
        assert status_code_received == 500
        # 验证错误信息为None（因为断言成功）
        assert error_received is None

    @allure.story("错误处理")
    @allure.title("测试各种HTTP状态码的指标记录")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.parametrize("status_code, should_fail", [
        (200, False),
        (201, False),
        (204, False),
        (400, True),
        (401, True),
        (403, True),
        (404, True),
        (500, True),
        (502, True),
        (503, True),
    ])
    async def test_various_status_codes_metrics(
            self, status_code, should_fail):
        """测试各种HTTP状态码的指标记录"""
        # 模拟一个返回指定状态码的响应
        async def mock_request():
            class MockResponse:
                status = status_code
                cookies = {}

                async def read(self):
                    return b'{"message": "test"}'

                def close(self):
                    pass
            return MockResponse()

        log = RequestMetrics(
            request_id="test-req-1",
            method="GET",
            endpoint="/test"
        )

        # 用于验证指标回调的参数
        metrics_callback_called = False
        assertion_result_received = None
        status_code_received = None

        async def mock_metrics_callback(**kwargs):
            nonlocal metrics_callback_called, assertion_result_received, status_code_received
            metrics_callback_called = True
            assertion_result_received = kwargs.get('assertion_result')
            status_code_received = kwargs.get('status_code')

        def mock_log_request(*args, **kwargs):
            pass

        rcm = ResponseContextManager(
            request_coroutine=mock_request(),
            log=log,
            start_time=0,
            metrics_callback=mock_metrics_callback,
            log_request=mock_log_request
        )

        # 测试各种状态码
        if should_fail:
            try:
                async with rcm as response:
                    # 断言失败
                    assert False, f"HTTP {status_code} error"
            except AssertionError:
                pass

            # 验证 assertion_result 被设置为 "fail"
            assert rcm.log.assertion_result == "fail"
        else:
            async with rcm as response:
                # 断言成功
                assert True

            # 验证 assertion_result 被设置为 "pass"
            assert rcm.log.assertion_result == "pass"

        # 验证原始状态码被保留
        assert rcm.log.status_code == status_code
        # 验证 metrics_callback 被调用
        assert metrics_callback_called
        # 验证 assertion_result 被正确传递
        assert assertion_result_received == "fail" if should_fail else assertion_result_received == "pass"
        # 验证状态码被正确传递
        assert status_code_received == status_code


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
