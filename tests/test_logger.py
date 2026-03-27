# encoding: utf-8

import os
import tempfile

import allure
import pytest

from aiotest.logger import ExtraFieldFormatter, Logger, logger


@allure.feature("ExtraFieldFormatter")
class TestExtraFieldFormatter:
    """ExtraFieldFormatter 类的测试用例"""

    @allure.story("初始化")
    @allure.title("测试 ExtraFieldFormatter 初始化")
    @allure.severity(allure.severity_level.NORMAL)
    def test_initialization(self):
        """测试 ExtraFieldFormatter 初始化时正确设置属性"""
        default_fmt = "%(asctime)s | %(levelname)s | %(message)s"
        field_fmt_dict = {
            "request_start": "%(asctime)s | %(levelname)s | %(message)s | %(request_start)s"
        }
        formatter = ExtraFieldFormatter(default_fmt, field_fmt_dict)
        assert formatter.default_fmt == default_fmt
        assert formatter.field_fmt_dict == field_fmt_dict

    @allure.story("格式化")
    @allure.title("测试默认格式")
    @allure.severity(allure.severity_level.NORMAL)
    def test_format_default(self):
        """测试使用默认格式"""
        import logging
        default_fmt = "%(asctime)s | %(levelname)s | %(message)s"
        field_fmt_dict = {
            "request_start": "%(asctime)s | %(levelname)s | %(message)s | %(request_start)s"
        }
        formatter = ExtraFieldFormatter(default_fmt, field_fmt_dict)

        record = logging.makeLogRecord(
            {"levelname": "INFO", "msg": "Test message"})
        formatted = formatter.format(record)
        assert "Test message" in formatted

    @allure.story("格式化")
    @allure.title("测试字段特定格式")
    @allure.severity(allure.severity_level.NORMAL)
    def test_format_with_field(self):
        """测试使用字段特定格式"""
        import logging
        default_fmt = "%(asctime)s | %(levelname)s | %(message)s"
        field_fmt_dict = {
            "request_start": "%(asctime)s | %(levelname)s | %(message)s | %(request_start)s"
        }
        formatter = ExtraFieldFormatter(default_fmt, field_fmt_dict)

        record = logging.makeLogRecord(
            {"levelname": "INFO", "msg": "Test message", "request_start": "2024-01-01 00:00:00"})
        formatted = formatter.format(record)
        assert "Test message" in formatted
        assert "2024-01-01 00:00:00" in formatted


@allure.feature("Logger")
class TestLogger:
    """Logger 类的测试用例"""

    @allure.story("初始化")
    @allure.title("测试 Logger 初始化")
    @allure.severity(allure.severity_level.NORMAL)
    def test_initialization(self):
        """测试 Logger 初始化时正确设置属性"""
        import logging
        with tempfile.TemporaryDirectory() as temp_dir:
            logger_instance = Logger(
                name="test_log",
                log_dir=temp_dir,
                log_level="DEBUG")
            assert logger_instance.name == "test_log"
            assert logger_instance.log_dir == temp_dir
            assert logger_instance.log_level == "DEBUG"
            assert logger_instance.logger is not None

            # 关闭日志处理器，释放文件锁
            for handler in logger_instance.logger.handlers:
                handler.close()
                logger_instance.logger.removeHandler(handler)

            # 清理日志记录器缓存
            if "test_log" in logging.Logger.manager.loggerDict:
                del logging.Logger.manager.loggerDict["test_log"]

    @allure.story("初始化")
    @allure.title("测试 Logger 重复初始化")
    @allure.severity(allure.severity_level.NORMAL)
    def test_initialization_repeated(self):
        """测试 Logger 重复初始化"""
        import logging
        with tempfile.TemporaryDirectory() as temp_dir:
            logger_instance = Logger(name="test_log", log_dir=temp_dir)
            # 再次初始化，应该不会重复添加处理器
            logger_instance._setup_logging()
            assert len(logger_instance.logger.handlers) == 2  # 文件处理器和标准输出处理器

            # 关闭日志处理器，释放文件锁
            for handler in logger_instance.logger.handlers:
                handler.close()
                logger_instance.logger.removeHandler(handler)

            # 清理日志记录器缓存
            if "test_log" in logging.Logger.manager.loggerDict:
                del logging.Logger.manager.loggerDict["test_log"]

    @allure.story("日志级别")
    @allure.title("测试设置日志级别")
    @allure.severity(allure.severity_level.NORMAL)
    def test_set_level(self):
        """测试设置日志级别"""
        import logging
        with tempfile.TemporaryDirectory() as temp_dir:
            logger_instance = Logger(
                name="test_log",
                log_dir=temp_dir,
                log_level="INFO")
            assert logger_instance.logger.level == 20  # INFO 级别

            logger_instance.setLevel("DEBUG")
            assert logger_instance.logger.level == 10  # DEBUG 级别

            # 关闭日志处理器，释放文件锁
            for handler in logger_instance.logger.handlers:
                handler.close()
                logger_instance.logger.removeHandler(handler)

            # 清理日志记录器缓存
            if "test_log" in logging.Logger.manager.loggerDict:
                del logging.Logger.manager.loggerDict["test_log"]

    @allure.story("日志级别")
    @allure.title("测试设置日志级别别名")
    @allure.severity(allure.severity_level.NORMAL)
    def test_set_level_alias(self):
        """测试设置日志级别（使用别名方法）"""
        import logging
        with tempfile.TemporaryDirectory() as temp_dir:
            logger_instance = Logger(
                name="test_log",
                log_dir=temp_dir,
                log_level="INFO")
            assert logger_instance.logger.level == 20  # INFO 级别

            logger_instance.set_level("DEBUG")
            assert logger_instance.logger.level == 10  # DEBUG 级别

            # 关闭日志处理器，释放文件锁
            for handler in logger_instance.logger.handlers:
                handler.close()
                logger_instance.logger.removeHandler(handler)

            # 清理日志记录器缓存
            if "test_log" in logging.Logger.manager.loggerDict:
                del logging.Logger.manager.loggerDict["test_log"]

    @allure.story("日志记录")
    @allure.title("测试记录 DEBUG 级别日志")
    @allure.severity(allure.severity_level.NORMAL)
    def test_debug(self):
        """测试记录 DEBUG 级别日志"""
        import logging
        with tempfile.TemporaryDirectory() as temp_dir:
            logger_instance = Logger(
                name="test_log",
                log_dir=temp_dir,
                log_level="DEBUG")
            logger_instance.debug("Debug message")
            # 这里我们只测试方法调用，不验证日志内容

            # 关闭日志处理器，释放文件锁
            for handler in logger_instance.logger.handlers:
                handler.close()
                logger_instance.logger.removeHandler(handler)

            # 清理日志记录器缓存
            if "test_log" in logging.Logger.manager.loggerDict:
                del logging.Logger.manager.loggerDict["test_log"]

    @allure.story("日志记录")
    @allure.title("测试记录 INFO 级别日志")
    @allure.severity(allure.severity_level.NORMAL)
    def test_info(self):
        """测试记录 INFO 级别日志"""
        import logging
        with tempfile.TemporaryDirectory() as temp_dir:
            logger_instance = Logger(name="test_log", log_dir=temp_dir)
            logger_instance.info("Info message")
            # 这里我们只测试方法调用，不验证日志内容

            # 关闭日志处理器，释放文件锁
            for handler in logger_instance.logger.handlers:
                handler.close()
                logger_instance.logger.removeHandler(handler)

            # 清理日志记录器缓存
            if "test_log" in logging.Logger.manager.loggerDict:
                del logging.Logger.manager.loggerDict["test_log"]

    @allure.story("日志记录")
    @allure.title("测试记录 WARNING 级别日志")
    @allure.severity(allure.severity_level.NORMAL)
    def test_warning(self):
        """测试记录 WARNING 级别日志"""
        import logging
        with tempfile.TemporaryDirectory() as temp_dir:
            logger_instance = Logger(name="test_log", log_dir=temp_dir)
            logger_instance.warning("Warning message")
            # 这里我们只测试方法调用，不验证日志内容

            # 关闭日志处理器，释放文件锁
            for handler in logger_instance.logger.handlers:
                handler.close()
                logger_instance.logger.removeHandler(handler)

            # 清理日志记录器缓存
            if "test_log" in logging.Logger.manager.loggerDict:
                del logging.Logger.manager.loggerDict["test_log"]

    @allure.story("日志记录")
    @allure.title("测试记录 ERROR 级别日志")
    @allure.severity(allure.severity_level.NORMAL)
    def test_error(self):
        """测试记录 ERROR 级别日志"""
        import logging
        with tempfile.TemporaryDirectory() as temp_dir:
            logger_instance = Logger(name="test_log", log_dir=temp_dir)
            logger_instance.error("Error message")
            # 这里我们只测试方法调用，不验证日志内容

            # 关闭日志处理器，释放文件锁
            for handler in logger_instance.logger.handlers:
                handler.close()
                logger_instance.logger.removeHandler(handler)

            # 清理日志记录器缓存
            if "test_log" in logging.Logger.manager.loggerDict:
                del logging.Logger.manager.loggerDict["test_log"]

    @allure.story("日志记录")
    @allure.title("测试记录 CRITICAL 级别日志")
    @allure.severity(allure.severity_level.NORMAL)
    def test_critical(self):
        """测试记录 CRITICAL 级别日志"""
        import logging
        with tempfile.TemporaryDirectory() as temp_dir:
            logger_instance = Logger(name="test_log", log_dir=temp_dir)
            logger_instance.critical("Critical message")
            # 这里我们只测试方法调用，不验证日志内容

            # 关闭日志处理器，释放文件锁
            for handler in logger_instance.logger.handlers:
                handler.close()
                logger_instance.logger.removeHandler(handler)

            # 清理日志记录器缓存
            if "test_log" in logging.Logger.manager.loggerDict:
                del logging.Logger.manager.loggerDict["test_log"]

    @allure.story("日志记录")
    @allure.title("测试获取日志记录器")
    @allure.severity(allure.severity_level.NORMAL)
    def test_get_logger(self):
        """测试获取日志记录器"""
        import logging
        with tempfile.TemporaryDirectory() as temp_dir:
            logger_instance = Logger(name="test_log", log_dir=temp_dir)
            log = logger_instance.get_logger()
            assert log is not None

            # 关闭日志处理器，释放文件锁
            for handler in logger_instance.logger.handlers:
                handler.close()
                logger_instance.logger.removeHandler(handler)

            # 清理日志记录器缓存
            if "test_log" in logging.Logger.manager.loggerDict:
                del logging.Logger.manager.loggerDict["test_log"]


@allure.feature("Global Logger")
class TestGlobalLogger:
    """全局日志记录器的测试用例"""

    @allure.story("全局日志")
    @allure.title("测试全局日志记录器")
    @allure.severity(allure.severity_level.NORMAL)
    def test_global_logger(self):
        """测试全局日志记录器"""
        assert logger is not None

    @allure.story("全局日志")
    @allure.title("测试全局日志记录")
    @allure.severity(allure.severity_level.NORMAL)
    def test_global_logger_logging(self):
        """测试使用全局日志记录器记录日志"""
        logger.info("Test global logger")
        # 这里我们只测试方法调用，不验证日志内容


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
