# encoding: utf-8

import allure
import pytest

from aiotest.exception import (AioTestError, InvalidRateError,
                               InvalidUserCountError, RunnerError,
                               create_exception)


@allure.feature("异常类测试")
class TestAioTestError:
    """测试 AioTestError 基础异常类"""

    @allure.story("初始化")
    @allure.title("测试基本初始化")
    @allure.severity(allure.severity_level.NORMAL)
    def test_init_basic(self):
        """测试基本初始化"""
        error = AioTestError("Test error")
        assert error.message == "Test error"
        assert error.error_code == "AioTestError"
        assert error.context == {}

    @allure.story("初始化")
    @allure.title("测试带错误码初始化")
    @allure.severity(allure.severity_level.NORMAL)
    def test_init_with_error_code(self):
        """测试带错误码初始化"""
        error = AioTestError("Test error", "TEST_ERROR")
        assert error.message == "Test error"
        assert error.error_code == "TEST_ERROR"

    @allure.story("初始化")
    @allure.title("测试带上下文初始化")
    @allure.severity(allure.severity_level.NORMAL)
    def test_init_with_context(self):
        """测试带上下文初始化"""
        context = {"key": "value"}
        error = AioTestError("Test error", "TEST_ERROR", context)
        assert error.message == "Test error"
        assert error.error_code == "TEST_ERROR"
        assert error.context == context

    @allure.story("字符串表示")
    @allure.title("测试 __str__ 方法")
    @allure.severity(allure.severity_level.NORMAL)
    def test_str_method(self):
        """测试 __str__ 方法"""
        error = AioTestError("Test error", "TEST_ERROR")
        assert str(error) == "[TEST_ERROR] Test error"


@allure.feature("异常类测试")
class TestRunnerError:
    """测试 RunnerError 异常类"""

    @allure.story("初始化")
    @allure.title("测试 RunnerError 初始化")
    @allure.severity(allure.severity_level.NORMAL)
    def test_init(self):
        """测试 RunnerError 初始化"""
        error = RunnerError("Runner error")
        assert error.message == "Runner error"
        assert error.error_code == "RunnerError"
        assert isinstance(error, AioTestError)


@allure.feature("异常类测试")
class TestInvalidUserCountError:
    """测试 InvalidUserCountError 异常类"""

    @allure.story("初始化")
    @allure.title("测试基本初始化")
    @allure.severity(allure.severity_level.NORMAL)
    def test_init_basic(self):
        """测试基本初始化"""
        error = InvalidUserCountError("Invalid user count")
        assert error.message == "Invalid user count"
        assert error.error_code == "INVALID_USER_COUNT"
        assert error.user_count is None
        assert error.context == {}

    @allure.story("初始化")
    @allure.title("测试带用户数量初始化")
    @allure.severity(allure.severity_level.NORMAL)
    def test_init_with_user_count(self):
        """测试带用户数量初始化"""
        error = InvalidUserCountError("Invalid user count", 100)
        assert error.message == "Invalid user count"
        assert error.error_code == "INVALID_USER_COUNT"
        assert error.user_count == 100
        assert error.context == {"user_count": 100}

    @allure.story("字符串表示")
    @allure.title("测试 __str__ 方法")
    @allure.severity(allure.severity_level.NORMAL)
    def test_str_method(self):
        """测试 __str__ 方法"""
        error = InvalidUserCountError("Invalid user count", 100)
        assert str(error) == "[INVALID_USER_COUNT] Invalid user count"


@allure.feature("异常类测试")
class TestInvalidRateError:
    """测试 InvalidRateError 异常类"""

    @allure.story("初始化")
    @allure.title("测试基本初始化")
    @allure.severity(allure.severity_level.NORMAL)
    def test_init_basic(self):
        """测试基本初始化"""
        error = InvalidRateError("Invalid rate")
        assert error.message == "Invalid rate"
        assert error.error_code == "INVALID_RATE"
        assert error.rate is None
        assert error.context == {}

    @allure.story("初始化")
    @allure.title("测试带速率初始化")
    @allure.severity(allure.severity_level.NORMAL)
    def test_init_with_rate(self):
        """测试带速率初始化"""
        error = InvalidRateError("Invalid rate", 10.5)
        assert error.message == "Invalid rate"
        assert error.error_code == "INVALID_RATE"
        assert error.rate == 10.5
        assert error.context == {"rate": 10.5}

    @allure.story("字符串表示")
    @allure.title("测试 __str__ 方法")
    @allure.severity(allure.severity_level.NORMAL)
    def test_str_method(self):
        """测试 __str__ 方法"""
        error = InvalidRateError("Invalid rate", 10.5)
        assert str(error) == "[INVALID_RATE] Invalid rate"


@allure.feature("异常工具函数测试")
class TestCreateException:
    """测试 create_exception 函数"""

    @allure.story("创建异常")
    @allure.title("测试创建基础 AioTestError")
    @allure.severity(allure.severity_level.NORMAL)
    def test_create_aio_test_error(self):
        """测试创建基础 AioTestError"""
        error = create_exception("UNKNOWN_ERROR", "Unknown error")
        assert isinstance(error, AioTestError)
        assert error.message == "Unknown error"
        assert error.error_code == "UNKNOWN_ERROR"

    @allure.story("创建异常")
    @allure.title("测试创建 InvalidUserCountError")
    @allure.severity(allure.severity_level.NORMAL)
    def test_create_invalid_user_count_error(self):
        """测试创建 InvalidUserCountError"""
        context = {"user_count": 100}
        error = create_exception(
            "INVALID_USER_COUNT",
            "Invalid user count",
            context)
        assert isinstance(error, InvalidUserCountError)
        assert error.message == "Invalid user count"
        assert error.error_code == "INVALID_USER_COUNT"
        assert error.user_count == 100

    @allure.story("创建异常")
    @allure.title("测试创建 InvalidRateError")
    @allure.severity(allure.severity_level.NORMAL)
    def test_create_invalid_rate_error(self):
        """测试创建 InvalidRateError"""
        context = {"rate": 10.5}
        error = create_exception("INVALID_RATE", "Invalid rate", context)
        assert isinstance(error, InvalidRateError)
        assert error.message == "Invalid rate"
        assert error.error_code == "INVALID_RATE"
        assert error.rate == 10.5

    @allure.story("创建异常")
    @allure.title("测试创建异常时上下文为 None")
    @allure.severity(allure.severity_level.NORMAL)
    def test_create_exception_with_none_context(self):
        """测试创建异常时上下文为 None"""
        error = create_exception(
            "INVALID_USER_COUNT",
            "Invalid user count",
            None)
        assert isinstance(error, InvalidUserCountError)
        assert error.user_count is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
